"""Fixed vocabularies shared across the backend.

Several of these are also held by the frontend, for building menus. The server
copies here are what values are actually validated against, so keep each in
step with the file named beside it.
"""

# Keep in step with frontend/src/constants/sports.js and the
# ck_fighters_sport CHECK constraint in models/fighter.py.
VALID_SPORTS = ("kickboxing", "mma", "boxing", "muaythai")

# The 48 ceremonial counties of England.
# Keep in step with frontend/src/constants/counties.js.
ENGLISH_COUNTIES = frozenset({
    'Bedfordshire', 'Berkshire', 'Bristol', 'Buckinghamshire',
    'Cambridgeshire', 'Cheshire', 'City of London', 'Cornwall', 'Cumbria',
    'Derbyshire', 'Devon', 'Dorset', 'Durham', 'East Riding of Yorkshire',
    'East Sussex', 'Essex', 'Gloucestershire', 'Greater London',
    'Greater Manchester', 'Hampshire', 'Herefordshire', 'Hertfordshire',
    'Isle of Wight', 'Kent', 'Lancashire', 'Leicestershire', 'Lincolnshire',
    'Merseyside', 'Norfolk', 'North Yorkshire', 'Northamptonshire',
    'Northumberland', 'Nottinghamshire', 'Oxfordshire', 'Rutland',
    'Shropshire', 'Somerset', 'South Yorkshire', 'Staffordshire', 'Suffolk',
    'Surrey', 'Tyne and Wear', 'Warwickshire', 'West Midlands',
    'West Sussex', 'West Yorkshire', 'Wiltshire', 'Worcestershire',
})
