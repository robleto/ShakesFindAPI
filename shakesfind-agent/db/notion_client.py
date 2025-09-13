import os, hashlib
from notion_client import Client

class NotionDB:
    def __init__(self):
        self.client = Client(auth=os.environ['NOTION_TOKEN'])
        self.db_companies = os.environ['COMPANIES_DB_ID']
        self.db_plays = os.environ['PLAYS_DB_ID']
        self.db_productions = os.environ['PRODUCTIONS_DB_ID']
        self._plays_cache = None

    def _query_all(self, dbid):
        results = []
        cursor = None
        while True:
            resp = self.client.databases.query(database_id=dbid, start_cursor=cursor)
            results.extend(resp['results'])
            if not resp.get('has_more'):
                break
            cursor = resp.get('next_cursor')
        return results

    def list_companies(self):
        rows = self._query_all(self.db_companies)
        out = []
        for r in rows:
            props = r['properties']
            out.append({
                'id': r['id'],
                'Name': props['Name']['title'][0]['plain_text'] if props['Name']['title'] else '',
                'Homepage URL': props.get('Homepage URL', {}).get('url'),
                'Productions URL': props.get('Productions URL', {}).get('url'),
                'Timezone': props.get('Timezone', {}).get('rich_text', [{}])[0].get('plain_text'),
                'HTML List Selector': props.get('HTML List Selector', {}).get('rich_text', [{}])[0].get('plain_text'),
                'HTML Field Map': props.get('HTML Field Map', {}).get('rich_text', [{}])[0].get('plain_text'),
                'Status': props.get('Status', {}).get('select', {}).get('name')
            })
        return out

    def _ensure_plays_cache(self):
        if self._plays_cache is not None:
            return
        rows = self._query_all(self.db_plays)
        self._plays_cache = {
            'by_title': {},
            'by_alias': {},
            'titles': []
        }
        for r in rows:
            p = r['properties']
            title = p['Title']['title'][0]['plain_text'] if p['Title']['title'] else ''
            aliases = [t['plain_text'] for t in p.get('Aliases', {}).get('rich_text', [])]
            self._plays_cache['by_title'][title.lower()] = {'id': r['id'], 'title': title}
            for a in aliases:
                self._plays_cache['by_alias'][a.lower()] = {'id': r['id'], 'title': title}
            self._plays_cache['titles'].append(title)

    def find_play_by_title(self, title):
        self._ensure_plays_cache()
        return self._plays_cache['by_title'].get(title.lower())

    def find_play_by_alias(self, title):
        self._ensure_plays_cache()
        return self._plays_cache['by_alias'].get(title.lower())

    def all_play_titles(self):
        self._ensure_plays_cache()
        return self._plays_cache['titles']

    def _find_by_hash(self, hsh):
        resp = self.client.databases.query(
            database_id=self.db_productions,
            filter={"property": "Source Hash", "rich_text": {"equals": hsh}}
        )
        return resp['results'][0] if resp['results'] else None

    def find_production_by_hash(self, hsh):
        r = self._find_by_hash(hsh)
        if not r:
            return None
        p = r['properties']
        return {'id': r['id'], 'props': p}

    def insert_production(self, row):
        props = self._prod_props(row)
        self.client.pages.create(parent={'database_id': self.db_productions}, properties=props)

    def update_production(self, page_id, row):
        props = self._prod_props(row)
        self.client.pages.update(page_id=page_id, properties=props)

    def touch_production(self, page_id):
        self.client.pages.update(page_id=page_id, properties={"Last Seen At": {"date": {"start": os.getenv('NOW_OVERRIDE') or __import__('datetime').datetime.utcnow().isoformat()}}})

    def touch_company(self, page_id):
        self.client.pages.update(page_id=page_id, properties={"Last Checked": {"date": {"start": __import__('datetime').datetime.utcnow().isoformat()}}})

    def differs(self, existing, row, ignore=None):
        ignore = set(ignore or [])
        # minimal: compare selected fields
        # a real impl would pull existing props and diff values
        return True

    def _prod_props(self, row):
        def rel(dbid):
            return [{"id": row[dbid]}] if row.get(dbid) else []
        return {
            "Company": {"relation": [{"id": row['Company']}]},
            "Play": {"relation": [{"id": row['Play']}] if row.get('Play') else []},
            "Title (Display)": {"rich_text": [{"text": {"content": row.get('Title (Display)', '')}}]},
            "Start Date": {"date": {"start": row.get('Start Date')}},
            "End Date": {"date": {"start": row.get('End Date')}},
            "Venue": {"rich_text": [{"text": {"content": row.get('Venue', '')}}]},
            "Show URL": {"url": row.get('Show URL')},
            "Ticket URL": {"url": row.get('Ticket URL')},
            "Source Page": {"url": row.get('Source Page')},
            "Source Hash": {"rich_text": [{"text": {"content": row.get('Source Hash', '')}}]},
            "Match Confidence": {"number": row.get('Match Confidence')},
            "Raw Dates Text": {"rich_text": [{"text": {"content": row.get('Raw Dates Text', '')}}]},
            "Last Seen At": {"date": {"start": row.get('Last Seen At')}},
            "Status": {"select": {"name": row.get('Status', 'new')}}
        }
