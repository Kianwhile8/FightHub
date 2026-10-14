"""Server-side copies of vocabularies the frontend also holds.

These exist so a value can be *validated*, not merely offered. The county list
lived only in frontend/src/constants/counties.js, which means it was a menu,
not a constraint: anything at all could be posted to the county field directly,
and was stored verbatim.

Keep in step with frontend/src/constants/counties.js. A mismatch surfaces as a
county the form offers and the server then refuses, so it fails loudly rather
than silently.
"""

# The 48 ceremonial counties of England, as the forms list them.
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
