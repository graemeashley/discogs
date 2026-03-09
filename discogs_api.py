'''
Add column selection and the same column choices for the master release and the eventual maserter exploded drop down.
This is an update to app.py, class.py, and index.html to pass the new columns.
'''


import os
import time
import requests
import pandas as pd
from datetime import date, datetime
import re 

class discogs:
    @staticmethod
    def pp_json(json_thing, sort=True, indents=4):
        import json
        if isinstance(json_thing, str):
            print(json.dumps(json.loads(json_thing), sort_keys=sort, indent=indents))
        else:
            print(json.dumps(json_thing, sort_keys=sort, indent=indents))

    @staticmethod
    def json_serial(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    @staticmethod
    def format_to_mm_ss(time_string):
        try:
            if not time_string or ":" not in time_string:
                return None
            parts = list(map(int, time_string.strip().split(":")))
            if len(parts) == 2:
                minutes, seconds = parts
            elif len(parts) == 3:
                hours, minutes, seconds = parts
                minutes += hours * 60
            else:
                return None
            return f"{minutes}:{seconds:02}"
        except:
            return None

    def __init__(self):
        self.url_ = "https://api.discogs.com/"
        self.key = os.getenv('DISCOGS_KEY')
        self.secret = os.getenv('DISCOGS_SECRET')
        self.headers = {
            "Authorization": f"Discogs key={self.key}, secret={self.secret}"
        }
        self.t = 10

    def rate_check(self, headers):
        used = int(headers.get('X-Discogs-Ratelimit-Remaining', 60))
        if used <= 5:
            time.sleep(self.t)
            self.t = min(self.t + 5, 60)
##the two functions below do the same thing..............
    def replace_master_versions_url(self, x):
        if re.search('releases',x):
            x = x.replace('api.discogs.com/releases', 'www.discogs.com/release')
            return(x)
        else:
            x = x.replace('api.discogs.com/masters', 'www.discogs.com/master')
            return(x)
    
    def replace_artist_versions_url(self, x):
        if re.search('releases',x):
            x = x.replace('api.discogs.com/releases', 'www.discogs.com/release')
            return(x)
        else:
            x = x.replace('api.discogs.com/masters', 'www.discogs.com/master')
            return(x)
        
    def get_release(self, release_id):
        url = f"{self.url_}releases/{release_id}"
        r = requests.get(url, headers=self.headers)
        self.rate_check(r.headers)
        r.raise_for_status()
        return r.json()

    def artist_releases(self, artist_id):
        releases = []
        page = 1
        per_page = 100
        while True:
            url = f"{self.url_}artists/{artist_id}/releases"
            r = requests.get(url, headers=self.headers, params={'per_page': per_page, 'page': page})
            self.rate_check(r.headers)
            r.raise_for_status()
            data = r.json()
            releases.extend(data.get('releases', []))
            if page >= data['pagination']['pages']:
                break
            page += 1
        return releases

    def export_label_release_csv(self, label_id, selected_cols = None):
        releases = []
        page = 1
        per_page = 100
        while True:
            url = f"{self.url_}labels/{label_id}/releases"
            r = requests.get(url, headers=self.headers, params={'per_page': per_page, 'page': page})
            self.rate_check(r.headers)
            r.raise_for_status()
            data = r.json()
            releases.extend(data.get('releases', []))
            if page >= data['pagination']['pages']:
                break
            page += 1
        df = pd.DataFrame(releases)
        df = df.drop_duplicates(keep = 'first')
        df['resource_url'] = df['resource_url'].apply(self.replace_master_versions_url)
        if selected_cols:
            df = df[[col for col in selected_cols if col in df.columns]]
        os.makedirs("output", exist_ok=True)
        path = f"output/label_{label_id}.csv"
        df.to_csv(path, index=False)
        return path
           

    def parsing_release_lists(self, data, return_df=False, selected_cols=None):
        rows = []
        exclusive = None
        for i in data['companies']:
            if i['entity_type_name'] == 'Exclusive Retailer':
                exclusive = i['name']  
        
        for d in data.get('tracklist', []):
            rows.append({
                'artist':        data.get('artists_sort'),
                'release_title': data.get('title'),
                'position':      d.get('position'),
                'track_title':   d.get('title'),
                'duration':      self.format_to_mm_ss(d.get('duration')),
                'release_id':    data.get('id'),
                'label':         data.get('labels', [{}])[0].get('name'),
                'format':        data.get('formats', [{}])[0].get('name'),
                'catno':         data.get('labels', [{}])[0].get('catno'),
                'release_url':   data.get('resource_url') or data.get('uri') or f"https://www.discogs.com/release/{data.get('id')}",
                'notes':         data.get('notes'),
                'exclusive':     exclusive,
                'country':       data.get('country'),
                'barcode':       data.get('identifiers', [{}])[0].get('value'),
                'release_year': data.get('released'),
                'instruments':  data.get('extraartists', [{}])[0].get('role')
            })

        df = pd.DataFrame(rows)
        if selected_cols:
            df = df[[col for col in selected_cols if col in df.columns]]

        os.makedirs("output", exist_ok=True)
        path = f"output/{data.get('id')}_release.csv"
        df.to_csv(path, index=False)

        return df if return_df else path

    def export_artist_releases_csv(self, artist_id, selected_cols=None):
        releases = self.artist_releases(artist_id)
        df = pd.DataFrame(releases)
        df['resource_url'] = df['resource_url'].apply(self.replace_artist_versions_url)
        if selected_cols:
            df = df[[col for col in selected_cols if col in df.columns]]
        os.makedirs("output", exist_ok=True)
        path = f"output/artist_{artist_id}.csv"
        df.to_csv(path, index=False)
        return path

    def export_master_versions_csv(self, master_id, selected_cols=None):
        all_versions = []
        page, per_page = 1, 100
        while True:
            r = requests.get(
                f"{self.url_}masters/{master_id}/versions",
                headers=self.headers,
                params={'per_page': per_page, 'page': page}
            )
            self.rate_check(r.headers)
            r.raise_for_status()
            data = r.json()
            all_versions.extend(data.get('versions', []))
            if page >= data['pagination']['pages']:
                break
            page += 1
        df = pd.DataFrame(all_versions)

        df['resource_url'] = df['resource_url'].apply(self.replace_master_versions_url)

        if selected_cols:
            df = df[[c for c in selected_cols if c in df.columns]]
    
        os.makedirs("output", exist_ok=True)
        path = f"output/master_{master_id}_versions.csv"
        df.to_csv(path, index=False)
        return path

    def export_master_release_details_csv(self, master_id):
        all_ids = []
        page = 1
        while True:
            url = f"{self.url_}masters/{master_id}/versions"
            r = requests.get(url, headers=self.headers, params={'per_page': 100, 'page': page})
            self.rate_check(r.headers)
            r.raise_for_status()
            data = r.json()
            all_ids.extend([v.get('id') for v in data.get('versions', [])])
            if page >= data['pagination']['pages']:
                break
            page += 1

        all_dfs = []
        for rid in all_ids:
            try:
                time.sleep(0.3)
                release_data = self.get_release(rid)
                df = self.parsing_release_lists(release_data, return_df=True)
                blank = pd.DataFrame([[""] * df.shape[1]], columns=df.columns)
                all_dfs.append(pd.concat([df, blank], ignore_index=True))
            except:
                continue

        if not all_dfs:
            raise Exception("No releases processed")
        final_df = pd.concat(all_dfs, ignore_index=True)
        os.makedirs("output", exist_ok=True)
        path = f"output/master_{master_id}_deep.csv"
        final_df.to_csv(path, index=False)
        return path

    def search_artist_and_release(self, artist_name, release_title):
        query = f"{artist_name} {release_title}".strip()
        params = {
            "q": query,
            "type": "release",
            "per_page": 10,
            "key": self.key,
            "secret": self.secret
        }
        r = requests.get(f"{self.url_}database/search", headers=self.headers, params=params)
        r.raise_for_status()
        return r.json().get("results", [])

'''
xx = discogs()
data = xx.get_release('5101485')
xx.parsing_release_lists(data)
'''
