# Canonical Shakespeare plays list with aliases and utility lookups
SHAKESPEARE_PLAYS = [
    {"slug": "hamlet", "title": "Hamlet", "aliases": ["The Tragedy of Hamlet", "Prince Hamlet"]},
    {"slug": "macbeth", "title": "Macbeth", "aliases": ["The Tragedy of Macbeth", "Mac Beth"]},
    {"slug": "romeoandjuliet", "title": "Romeo and Juliet", "aliases": ["R&J", "Romeo & Juliet"]},
    {"slug": "midsummer", "title": "A Midsummer Night's Dream", "aliases": ["A Midsummer Night’s Dream", "Midsummer", "MND"]},
    {"slug": "muchado", "title": "Much Ado About Nothing", "aliases": ["Much Ado"]},
    {"slug": "twelfthnight", "title": "Twelfth Night", "aliases": ["Twelfth Night or What You Will", "12th Night"]},
    {"slug": "taming", "title": "The Taming of the Shrew", "aliases": ["Taming of the Shrew", "Taming"]},
    {"slug": "merchant", "title": "The Merchant of Venice", "aliases": ["Merchant of Venice", "Merchant"]},
    {"slug": "tempest", "title": "The Tempest", "aliases": ["Tempest"]},
    {"slug": "asyoulikeit", "title": "As You Like It", "aliases": []},
    {"slug": "allswell", "title": "All's Well That Ends Well", "aliases": ["Alls Well"]},
    {"slug": "comedyoferrors", "title": "The Comedy of Errors", "aliases": ["Comedy of Errors"]},
    {"slug": "loveslabourslost", "title": "Love's Labour's Lost", "aliases": ["Loves Labours Lost", "Love’s Labor’s Lost"]},
    {"slug": "twoGents", "title": "The Two Gentlemen of Verona", "aliases": ["Two Gentlemen of Verona", "Two Gents"]},
    {"slug": "merrywives", "title": "The Merry Wives of Windsor", "aliases": ["Merry Wives"]},
    {"slug": "measureformeasure", "title": "Measure for Measure", "aliases": []},
    {"slug": "antonyandcleopatra", "title": "Antony and Cleopatra", "aliases": []},
    {"slug": "coriolanus", "title": "Coriolanus", "aliases": []},
    {"slug": "juliuscaesar", "title": "Julius Caesar", "aliases": []},
    {"slug": "kinglear", "title": "King Lear", "aliases": []},
    {"slug": "othello", "title": "Othello", "aliases": []},
    {"slug": "timon", "title": "Timon of Athens", "aliases": ["Timon"]},
    {"slug": "titus", "title": "Titus Andronicus", "aliases": ["Titus"]},
    {"slug": "kingjohn", "title": "King John", "aliases": []},
    {"slug": "richardii", "title": "Richard II", "aliases": ["Richard 2"]},
    {"slug": "henryiv1", "title": "Henry IV, Part 1", "aliases": ["Henry IV Part 1", "Henry IV Pt 1", "1 Henry IV"]},
    {"slug": "henryiv2", "title": "Henry IV, Part 2", "aliases": ["Henry IV Part 2", "Henry IV Pt 2", "2 Henry IV"]},
    {"slug": "henryv", "title": "Henry V", "aliases": []},
    {"slug": "henryvi1", "title": "Henry VI, Part 1", "aliases": ["1 Henry VI"]},
    {"slug": "henryvi2", "title": "Henry VI, Part 2", "aliases": ["2 Henry VI"]},
    {"slug": "henryvi3", "title": "Henry VI, Part 3", "aliases": ["3 Henry VI"]},
    {"slug": "richardiii", "title": "Richard III", "aliases": ["Richard 3"]},
    {"slug": "henryviii", "title": "Henry VIII", "aliases": ["Henry 8"]},
    {"slug": "cymbeline", "title": "Cymbeline", "aliases": []},
    {"slug": "pericles", "title": "Pericles", "aliases": []},
    {"slug": "wintersTale", "title": "The Winter's Tale", "aliases": ["Winters Tale"]},
    {"slug": "twonoblekinsmen", "title": "The Two Noble Kinsmen", "aliases": ["Two Noble Kinsmen", "Two Nobles"]},
]

# Build lookups
ALIAS_TO_CANON = {}
CANON_TITLES = []
for p in SHAKESPEARE_PLAYS:
    CANON_TITLES.append(p['title'])
    ALIAS_TO_CANON[p['title'].lower()] = p['title']
    for a in p['aliases']:
        ALIAS_TO_CANON[a.lower()] = p['title']

__all__ = [
    'SHAKESPEARE_PLAYS',
    'ALIAS_TO_CANON',
    'CANON_TITLES'
]
