from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session
import configparser
import requests
import time
import json


# import logging
# logging.basicConfig()
# log = logging.getLogger()
# log.setLevel('DEBUG')


class BitBucketAuth:
    api_uri = "https://api.bitbucket.org/2.0"
    client_id = None
    client_secret = None
    token = None
    parser = None
    filename = None
    username = None

    def __init__(self, filename):
        self.filename = filename
        self.parser = configparser.ConfigParser()
        self.parser.read(filename)
        self.client_id = self.parser.get('default', 'client_id')
        self.client_secret = self.parser.get('default', 'client_secret')
        self.username = self.parser.get('default', 'username')
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

    def get_repositories(self):
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
            return repos


bb = BitBucketAuth('config.ini')

rep = bb.get_repositories()

print(json.dumps(rep, indent=2))
