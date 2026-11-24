"""SQLAlchemy models and theDatabase compatibility facade.

The tables, columns and public ``Database`` methods are unchanged from the
original sqlite implementation. Routes and services keep calling ``db.<method>``
while SQLAlchemy handles the actual persistence (SQLite locally, Postgres in
production).
"""
import hashlib
import hmac
import json
import os
import sqlite3
from datetime import datetime

from sqlalchemy import event, func, or_, text
from sqlalchemy.engine import Engine
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import sqlalchemy
from app.services.db_migration import copy_legacy_sqlite_data


@event.listens_for(Engine, 'connect')
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """SQLite needs FK enforcement enabled per connection."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()


class BaseModel(sqlalchemy.Model):
    __abstract__ = True

    def to_dict(self):
        """Dict in the same shape the sqlite Row-based implementation returned."""
        values = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat(sep=' ', timespec='seconds')
            values[column.name] = value
        return values


class User(BaseModel):
    __tablename__ = 'users'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    username = sqlalchemy.Column(sqlalchemy.String, unique=True, nullable=False)
    email = sqlalchemy.Column(sqlalchemy.String, unique=True, nullable=False)
    password = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    full_name = sqlalchemy.Column(sqlalchemy.String)
    phone = sqlalchemy.Column(sqlalchemy.String)
    education = sqlalchemy.Column(sqlalchemy.String)
    stream = sqlalchemy.Column(sqlalchemy.String)
    created_at = sqlalchemy.Column(sqlalchemy.TIMESTAMP, server_default=func.current_timestamp())
    last_login = sqlalchemy.Column(sqlalchemy.TIMESTAMP)
    is_admin = sqlalchemy.Column(sqlalchemy.Integer, default=0)

    psychometric_results = sqlalchemy.orm.relationship(
        'PsychometricResult', backref='user', cascade='all, delete-orphan', passive_deletes=True
    )
    quiz_results = sqlalchemy.orm.relationship(
        'QuizResult', backref='user', cascade='all, delete-orphan', passive_deletes=True
    )
    iq_test_results = sqlalchemy.orm.relationship(
        'IQTestResult', backref='user', cascade='all, delete-orphan', passive_deletes=True
    )
    admin_logs = sqlalchemy.orm.relationship(
        'AdminLog', cascade='all, delete-orphan', passive_deletes=True
    )


class PsychometricResult(BaseModel):
    __tablename__ = 'psychometric_results'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    user_id = sqlalchemy.Column(
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
    )
    test_date = sqlalchemy.Column(sqlalchemy.TIMESTAMP, server_default=func.current_timestamp())
    personality = sqlalchemy.Column(sqlalchemy.Text)
    interests = sqlalchemy.Column(sqlalchemy.Text)
    aptitudes = sqlalchemy.Column(sqlalchemy.Text)
    work_styles = sqlalchemy.Column(sqlalchemy.Text)
    value_data = sqlalchemy.Column(sqlalchemy.Text)
    raw_answers = sqlalchemy.Column(sqlalchemy.Text)
    ai_summary = sqlalchemy.Column(sqlalchemy.Text)
    career_matches = sqlalchemy.Column(sqlalchemy.Text)


class QuizResult(BaseModel):
    __tablename__ = 'quiz_results'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    user_id = sqlalchemy.Column(
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
    )
    test_date = sqlalchemy.Column(sqlalchemy.TIMESTAMP, server_default=func.current_timestamp())
    answers = sqlalchemy.Column(sqlalchemy.Text)
    recommendations = sqlalchemy.Column(sqlalchemy.Text)
    ai_summary = sqlalchemy.Column(sqlalchemy.Text)


class IQTestResult(BaseModel):
    __tablename__ = 'iq_test_results'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    user_id = sqlalchemy.Column(
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
    )
    test_date = sqlalchemy.Column(sqlalchemy.TIMESTAMP, server_default=func.current_timestamp())
    iq_score = sqlalchemy.Column(sqlalchemy.Integer)
    correct_count = sqlalchemy.Column(sqlalchemy.Integer)
    section_scores = sqlalchemy.Column(sqlalchemy.Text)
    answers = sqlalchemy.Column(sqlalchemy.Text)
    time_taken = sqlalchemy.Column(sqlalchemy.Integer)


class AdminLog(BaseModel):
    __tablename__ = 'admin_logs'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    admin_id = sqlalchemy.Column(
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
    )
    action = sqlalchemy.Column(sqlalchemy.String)
    target_user_id = sqlalchemy.Column(sqlalchemy.Integer)
    timestamp = sqlalchemy.Column(sqlalchemy.TIMESTAMP, server_default=func.current_timestamp())


class _RowShim:
    """Mapping-style row so old ``row['column']`` call sites keep working."""

    def __init__(self, values):
        self._values = dict(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._values.values())[key]
        return self._values[key]

    def keys(self):
        return self._values.keys()

    def get(self, key, default=None):
        return self._values.get(key, default)

    def __iter__(self):
        return iter(self._values)


class _ResultShim:
    def __init__(self, result):
        self._result = result

    def fetchone(self):
        row = self._result.mappings().first()
        return _RowShim(row) if row is not None else None

    def fetchall(self):
        return [_RowShim(row) for row in self._result.mappings().all()]

    @property
    def lastrowid(self):
        try:
            return self._result.inserted_primary_key[0]
        except (AttributeError, IndexError, TypeError):
            return None


class _ConnectionShim:
    """Minimal DBAPI-style wrapper over a SQLAlchemy connection.

    Translates the original ``?`` placeholders to named parameters so legacy
    raw-SQL call sites (tests and helper scripts) remain valid on Postgres too.
    """

    def __init__(self, connection):
        self._connection = connection

    def execute(self, statement, params=()):
        values = {}
        pieces = []
        index = 0
        for character in statement:
            if character == '?':
                name = f'p{index}'
                index += 1
                values[name] = params[index - 1] if index - 1 < len(params) else None
                pieces.append(f':{name}')
            else:
                pieces.append(character)
        return _ResultShim(self._connection.execute(text(''.join(pieces)), values))

    def commit(self):
        self._connection.commit()

    def close(self):
        self._connection.close()


class Database:
    """Public database API used by services and routes."""

    def __init__(self, db_path=None, app=None):
        if db_path:
            self.db_path = os.path.abspath(db_path)
        else:
            self.db_path = None
        self.app = app
        if app is not None:
            self.init_app(app)

    def _context(self):
        if self.app is None:
            from app import app as flask_app
            self.app = flask_app
        return self.app.app_context()

    def init_app(self, app):
        self.app = app
        uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if uri.startswith('sqlite:///'):
            from sqlalchemy.engine import make_url
            self.db_path = os.path.abspath(make_url(uri).database)
        if os.getenv('SKIP_DB_CREATE'):
            return
        with app.app_context():
            sqlalchemy.create_all()
            copy_legacy_sqlite_data(sqlalchemy.session)
            self._seed_admin()
        print('✅ Database initialized successfully!')

    def _seed_admin(self):
        username = os.getenv('ADMIN_USERNAME')
        email = os.getenv('ADMIN_EMAIL')
        password = os.getenv('ADMIN_PASSWORD')
        if not (username and email and password):
            return
        with self._context():
            if User.query.filter_by(is_admin=1).first():
                return
            sqlalchemy.session.add(User(
                username=username,
                email=email,
                password=generate_password_hash(password),
                full_name='Administrator',
                is_admin=1,
            ))
            sqlalchemy.session.commit()

    def get_connection(self):
        with self._context():
            return _ConnectionShim(sqlalchemy.engine.connect())

    # ============ USER MANAGEMENT ============
    def create_user(self, username, email, password, full_name=None, phone=None,
                    education=None, stream=None):
        try:
            with self._context():
                user = User(
                    username=username,
                    email=email,
                    password=generate_password_hash(password),
                    full_name=full_name,
                    phone=phone,
                    education=education,
                    stream=stream,
                )
                sqlalchemy.session.add(user)
                sqlalchemy.session.commit()
                return {'success': True, 'user_id': user.id}
        except Exception as exc:
            return {'success': False, 'error': str(exc)}

    def authenticate_user(self, username, password):
        with self._context():
            user = User.query.filter(
                or_(User.username == username, User.email == username)
            ).first()
            if not user:
                return None

            stored = user.password or ''
            if stored.startswith(('pbkdf2:', 'scrypt:', 'argon2')):
                valid = check_password_hash(stored, password)
            else:
                legacy = hashlib.sha256(password.encode()).hexdigest()
                valid = hmac.compare_digest(stored, legacy)
                if valid:
                    try:
                        self.update_password_hash(user.id, generate_password_hash(password))
                    except Exception as exc:
                        print(f'Could not upgrade legacy password hash: {exc}')

            if not valid:
                return None

            self.update_last_login(user.id)
            return user.to_dict()

    def update_password_hash(self, user_id, password_hash):
        with self._context():
            user = sqlalchemy.session.get(User, user_id)
            if user:
                user.password = password_hash
                sqlalchemy.session.commit()
        return True

    def update_last_login(self, user_id):
        with self._context():
            user = sqlalchemy.session.get(User, user_id)
            if user:
                user.last_login = datetime.utcnow()
                sqlalchemy.session.commit()

    def get_user_by_id(self, user_id):
        with self._context():
            user = sqlalchemy.session.get(User, user_id)
            return user.to_dict() if user else None

    def get_user_by_username(self, username):
        with self._context():
            user = User.query.filter_by(username=username).first()
            return user.to_dict() if user else None

    def get_all_users(self, admin_only=False):
        with self._context():
            users = User.query.filter_by(is_admin=1 if admin_only else 0).order_by(
                User.created_at.desc()
            ).all()
            return [user.to_dict() for user in users]

    def update_user(self, user_id, **kwargs):
        allowed_fields = ['full_name', 'phone', 'education', 'stream', 'email']
        with self._context():
            user = sqlalchemy.session.get(User, user_id)
            if user:
                for key, value in kwargs.items():
                    if key in allowed_fields and value:
                        setattr(user, key, value)
                sqlalchemy.session.commit()
        return True

    def delete_user(self, user_id):
        with self._context():
            user = sqlalchemy.session.get(User, user_id)
            if user:
                sqlalchemy.session.delete(user)
                sqlalchemy.session.commit()
        return True

    # ============ PSYCHOMETRIC TEST RESULTS ============
    def save_psychometric_result(self, user_id, personality, interests, aptitudes,
                                 work_styles, value_data, raw_answers, ai_summary,
                                 career_matches):
        with self._context():
            result = PsychometricResult(
                user_id=user_id,
                personality=json.dumps(personality),
                interests=json.dumps(interests),
                aptitudes=json.dumps(aptitudes),
                work_styles=json.dumps(work_styles),
                value_data=json.dumps(value_data),
                raw_answers=json.dumps(raw_answers),
                ai_summary=ai_summary,
                career_matches=json.dumps(career_matches),
            )
            sqlalchemy.session.add(result)
            sqlalchemy.session.commit()
            return result.id

    def get_psychometric_results(self, user_id, limit=10):
        with self._context():
            rows = PsychometricResult.query.filter_by(user_id=user_id).order_by(
                PsychometricResult.test_date.desc()
            ).limit(limit).all()
            results = [row.to_dict() for row in rows]
        for result in results:
            for field in ('personality', 'interests', 'aptitudes', 'work_styles',
                          'value_data'):
                result[field] = json.loads(result[field]) if result[field] else {}
            result['career_matches'] = (
                json.loads(result['career_matches']) if result['career_matches'] else []
            )
        return results

    # ============ QUIZ RESULTS ============
    def save_quiz_result(self, user_id, answers, recommendations, ai_summary):
        with self._context():
            result = QuizResult(
                user_id=user_id,
                answers=json.dumps(answers),
                recommendations=json.dumps(recommendations),
                ai_summary=ai_summary,
            )
            sqlalchemy.session.add(result)
            sqlalchemy.session.commit()
            return result.id

    def get_quiz_results(self, user_id, limit=10):
        with self._context():
            rows = QuizResult.query.filter_by(user_id=user_id).order_by(
                QuizResult.test_date.desc()
            ).limit(limit).all()
            results = [row.to_dict() for row in rows]
        for result in results:
            result['answers'] = json.loads(result['answers']) if result['answers'] else {}
            result['recommendations'] = (
                json.loads(result['recommendations']) if result['recommendations'] else []
            )
        return results

    # ============ IQ TEST RESULTS ============
    def save_iq_test_result(self, user_id, iq_score, correct_count, section_scores,
                            answers, time_taken):
        try:
            with self._context():
                result = IQTestResult(
                    user_id=user_id,
                    iq_score=iq_score,
                    correct_count=correct_count,
                    section_scores=json.dumps(section_scores),
                    answers=json.dumps(answers),
                    time_taken=time_taken,
                )
                sqlalchemy.session.add(result)
                sqlalchemy.session.commit()
                result_id = result.id
            return result_id
        except Exception as exc:
            print(f'❌ Error saving IQ test result: {exc}')
            return None

    def get_iq_test_results(self, user_id, limit=5):
        try:
            with self._context():
                rows = IQTestResult.query.filter_by(user_id=user_id).order_by(
                    IQTestResult.test_date.desc()
                ).limit(limit).all()
                results = [row.to_dict() for row in rows]
            for result in results:
                result['section_scores'] = (
                    json.loads(result['section_scores']) if result['section_scores'] else {}
                )
                result['answers'] = json.loads(result['answers']) if result['answers'] else {}
            return results
        except Exception as exc:
            print(f'❌ Error getting IQ test results: {exc}')
            return []

    def get_latest_iq_test_result(self, user_id):
        results = self.get_iq_test_results(user_id, limit=1)
        return results[0] if results else None

    def get_iq_test_stats(self, user_id):
        try:
            with self._context():
                stats = sqlalchemy.session.query(
                    func.count(IQTestResult.id).label('total_tests'),
                    func.avg(IQTestResult.iq_score).label('avg_score'),
                    func.max(IQTestResult.iq_score).label('highest_score'),
                    func.min(IQTestResult.iq_score).label('lowest_score'),
                ).filter(IQTestResult.user_id == user_id).one()
                return {
                    'total_tests': stats.total_tests,
                    'avg_score': stats.avg_score,
                    'highest_score': stats.highest_score,
                    'lowest_score': stats.lowest_score,
                }
        except Exception as exc:
            print(f'❌ Error getting IQ test stats: {exc}')
            return None

    # ============ ADMIN LOGS ============
    def log_admin_action(self, admin_id, action, target_user_id=None):
        with self._context():
            sqlalchemy.session.add(AdminLog(
                admin_id=admin_id,
                action=action,
                target_user_id=target_user_id,
            ))
            sqlalchemy.session.commit()

    def get_admin_logs(self, limit=50):
        with self._context():
            rows = sqlalchemy.session.query(
                AdminLog, User.username.label('admin_name')
            ).join(User, AdminLog.admin_id == User.id).order_by(
                AdminLog.timestamp.desc()
            ).limit(limit).all()
            logs = []
            for log, admin_name in rows:
                entry = log.to_dict()
                entry['admin_name'] = admin_name
                logs.append(entry)
            return logs

    # ============ STATISTICS ============
    def get_stats(self):
        with self._context():
            stats = {
                'total_users': User.query.filter_by(is_admin=0).count(),
                'psychometric_tests': PsychometricResult.query.count(),
                'quiz_tests': QuizResult.query.count(),
                'iq_tests': IQTestResult.query.count(),
                'total_admins': User.query.filter_by(is_admin=1).count(),
            }
            recent = User.query.filter_by(is_admin=0).order_by(
                User.created_at.desc()
            ).limit(5).all()
            stats['recent_users'] = [user.to_dict() for user in recent]
            return stats
