from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
import configparser
import requests
import time
import json
import os
import git
from git import RemoteProgress


class CustomProgress(RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=''):
        if message:
            print(message)


class BitBucketAPI:
    api_uri = "https://api.bitbucket.org/2.0"
    client_id = None
    client_secret = None
    token = None
    parser = None
    filename = None
    username = None
    repo_file = None

    def __init__(self, filename):
        self.filename = filename
        self.parser = configparser.ConfigParser()
        self.parser.read(filename)
        self.client_id = self.parser.get('default', 'client_id')
        self.client_secret = self.parser.get('default', 'client_secret')
        self.username = self.parser.get('default', 'username')
        self.repo_file = self.parser['default'].get('repo_file', 'repo_cache.json')
        if self.parser.has_option('default', 'token'):
            self.token = json.loads(self.parser.get('default', 'token'))

    def retrieve_auth_token(self):
        client = BackendApplicationClient(client_id=self.client_id)
        oauth = OAuth2Session(client=client)

        self.token = oauth.fetch_token(
            token_url='https://bitbucket.org/site/oauth2/access_token',
            client_id=self.client_id,
            client_secret=self.client_secret)
        self.parser.set('default', 'token', json.dumps(self.token))
        with open(self.filename, 'w+') as f:
            self.parser.write(f)

    def auth_token(self):
        if self.token is None or self.token['expires_at'] < time.time():
            self.retrieve_auth_token()

        return self.token['access_token']

    def api_get(self, uri):
        headers = {'Authorization': 'Bearer {}'.format(self.auth_token())}
        ret = requests.get(self.api_uri + uri, headers=headers)
        if ret.status_code == 401:
            self.token = None
            headers = {'Authorization': 'Bearer {}'.format(self.auth_token())}
            ret = requests.get(self.api_uri + uri, headers=headers)
        return ret

    def get_repositories(self, force=False):
        if os.path.exists(self.repo_file) and not force:
            with open(self.repo_file) as f:
                return json.load(f)
        repos = []
        pagenum = 1
        while True:
            ret = self.api_get('/repositories/{}?page={}'.format(self.username, pagenum))
            if ret.status_code != 200:
                return repos
            ret = ret.json()
            repos += ret['values']
            if 'next' in ret:
                pagenum += 1
                continue
            with open(self.repo_file, 'w+') as f:
                json.dump(repos, f, indent=2)
            return repos

    def get_filtered_repositories(self):
        ret = []
        for r in self.get_repositories():
            if r['scm'] != 'git':
                continue
            ret.append({
                'url': [x['href'] for x in r['links']['clone'] if x['name'] == 'ssh'][0],
                'name': r['name'],
                'full_name': r['full_name'],
                'updated': r['updated_on']
            })
        return ret


def git_prog(p1, p2, p3, p4):
    print(p1, p2, p3, p4)


def backup_repository(repo):
    url = repo['url']
    backup_dir = os.path.join('backup', repo['full_name'])

    # Clone new repo or update existing one
    if not os.path.exists(backup_dir):
        print("Cloning {}".format(backup_dir))
        repo = git.Repo.clone_from(url, backup_dir, progress=CustomProgress())
    else:
        print("Pulling {}".format(backup_dir))
        repo = git.Repo(backup_dir)
        o = repo.remotes.origin
        o.fetch()
        o.pull()

    # track and pull new branches
    local_branches = [r.name for r in repo.branches]
    remote_branches = [i.name for i in repo.remote('origin').fetch()]
    for r in remote_branches:
        s = r[7:]
        if s not in local_branches:
            print("tracking branch {}".format(s))
            repo.git.checkout(s)


def backup_repositories(repos):
    for r in repos:
        backup_repository(r)


bb = BitBucketAPI('config.ini')

repos = bb.get_filtered_repositories()
backup_repositories(repos)
