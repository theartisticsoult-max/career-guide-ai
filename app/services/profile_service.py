"""Profile persistence and completion checks."""
from app.extensions import sqlalchemy
from app.models import Profile

STAGES = ('class10', 'class12', 'college')


def get_profile(user_id):
    profile = Profile.query.filter_by(user_id=user_id).first()
    return profile.to_dict() if profile else None


def needs_profile(user_id):
    """True until the user has filled the one-time profile form."""
    return get_profile(user_id) is None


def save_profile(user_id, stage, stream=None, interests_text=None, city=None,
                 country=None, region=None):
    """Create or update the user's profile. Routes validate before calling."""
    if stage not in STAGES:
        return {'success': False, 'error': 'Invalid stage'}

    profile = Profile.query.filter_by(user_id=user_id).first()
    if profile is None:
        profile = Profile(user_id=user_id)
        sqlalchemy.session.add(profile)

    profile.stage = stage
    profile.stream = stream or None
    profile.interests_text = interests_text or None
    profile.city = city or None
    profile.country = country or None
    profile.region = region or None
    sqlalchemy.session.commit()
    return {'success': True, 'profile': profile.to_dict()}
