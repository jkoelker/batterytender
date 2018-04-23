# -*- coding:utf-8 -*-

# Copyright (c) 2018 Jason Kölker
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import urllib.parse

import dateutil.parser
import requests
import requests.auth
import ttldict


# NOTE(jkoelker) Althogh the mobile app uses http, the endpoint supports https
#                so we use that, because, you know, its 2018
HOST = 'https://btconnectedpower.com'
LOGIN_PATH = '/api/users/login'
CHARGER_PATH = '/api/charger/status'
MONITOR_PATH = '/api/monitor/status'


class AuthorizationError(Exception):
    def __init__(self, response):
        super(AuthorizationError, self).__init__('Authorization Falied')
        self.response = response


class BatteryTenderAuth(requests.auth.AuthBase):
    def __init__(self, email, password, callback=None):
        self._params = {'email': email, 'password': password}
        self._callback = callback
        self.token = None
        self._enc_token = None

    def _handle(self, r, **kwargs):
        if r.status_code == 401:
            r.content
            r.close()

            auth = requests.Request(method='POST',
                                    url='{}{}'.format(HOST, LOGIN_PATH),
                                    params=self._params)

            _r = r.connection.send(auth.prepare(), **kwargs)
            _r.history.append(r)
            _r.request = auth

            if _r.status_code == 401:
                raise AuthorizationError(_r)

            if _r.status_code != 200:
                return r

            data = _r.json()
            self.token = data.get('token')
            self._enc_token = urllib.parse.urlencode({'token': self.token})

            if self._callback:
                self._callback(data)

            redo = r.request.copy()
            redo.prepare_url(redo.url, {'token': self.token})

            _r.content
            _r.close()

            return _r.connection.send(redo, **kwargs)

        return r

    def __call__(self, r):
        if self._enc_token and 'token' not in r.url:
            # NOTE(jkoelker) since this request is prepared, requests has
            #                has already validataed the url and raised
            #                parse errors. Its ok to just use urllib.parse
            (scheme,
             netloc,
             path,
             params,
             query,
             fragment) = urllib.parse.urlparse(r.url)

            if query:
                query = '%s&%s' % (query, self._enc_token)
            else:
                query = self._enc_token

            url_tuple = (scheme, netloc, path, params, query, fragment)
            r.url = urllib.parse.urlunparse(url_tuple)

        r.register_hook('response', self._handle)
        return r


class BTBase(object):
    def __init__(self, device_id, bt_api):
        self.device_id = device_id
        self._bt_api = bt_api

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self._repr_name)

    @property
    def _repr_name(self):
        return self.device_id


# NOTE(jkoelker) This is untested, I do not have a charger
#                PR's welcome.
class Charger(BTBase):
    pass


class Monitor(BTBase):
    @property
    def _monitor(self):
        return self._bt_api._monitor(self.device_id).get('monitor', {})

    @property
    def current(self):
        c = self._bt_api._monitor(self.device_id)

        if not c:
            return {}

        if 'date' in c and 'id' in c and 'soc' in c and 'voltage' in c:
            return {'date': c['date'],
                    'id': c['id'],
                    'soc': c['soc'],
                    'voltage': c['voltage']}

        return {}

    @property
    def created(self):
        return self._monitor.get('createdAt')

    @property
    def updated(self):
        return self._monitor.get('updated')

    @property
    def name(self):
        return self._monitor.get('name')

    @property
    def history(self):
        return self._bt_api._monitor_history(self.device_id)

    @property
    def date(self):
        return self._bt_api._monitor(self.device_id).get('date')

    @property
    def soc(self):
        return self._bt_api._monitor(self.device_id).get('soc')

    @property
    def voltage(self):
        return self._bt_api._monitor(self.device_id).get('voltage')


class BatteryTender(object):
    def __init__(self, email, password, cache_ttl=600):
        self._cache_ttl = cache_ttl

        self._charger_cache = ttldict.TTLOrderedDict(self._cache_ttl)
        self._chargers_cache = ttldict.TTLOrderedDict(self._cache_ttl)

        self._monitor_cache = ttldict.TTLOrderedDict(self._cache_ttl)
        self._monitors_cache = ttldict.TTLOrderedDict(self._cache_ttl)

        def parse_status_history(item):
            status_history = item.get('statusHistory', [])
            parsed = []
            for status in status_history:
                if 'date' in status:
                    status['date'] = dateutil.parser.parse(status['date'])

                parsed.append(status)

            return parsed

        def callback(data):
            for monitor in data.get('monitors', []):
                if 'deviceId' not in monitor:
                    continue

                monitor['statusHistory'] = parse_status_history(monitor)
                self._monitors_cache[monitor['deviceId']] = monitor

            # NOTE(jkoelker) This is untested, I do not have a charger
            #                PR's welcome.
            for charger in data.get('chargers', []):
                if 'deviceId' not in charger:
                    continue

                charger['statusHistory'] = parse_status_history(charger)
                self._chargers_cache[charger['deviceId']] = charger

        self._session = requests.Session()
        self._session.auth = BatteryTenderAuth(email, password,
                                               callback=callback)

    def _request(self, verb, path, params=None):
        url = '{}{}'.format(HOST, path)
        response = self._session.request(verb, url, params=params,
                                         allow_redirects=False)

        if response.status_code == 200:
            return response.json()

        return {}

    def _history(self, device_id, cache):
        if device_id not in cache.keys():
            self.refresh_cache()

        device = cache.get(device_id, {})

        return device.get('statusHistory', [])

    def _charger_history(self, device_id):
        return self._history(device_id, self._monitors_cache)

    def _monitor_history(self, device_id):
        return self._history(device_id, self._monitors_cache)

    @staticmethod
    def _prepare_device(device, key):
        if 'date' in device:
            device['date'] = dateutil.parser.parse(device['date'])

        if key in device:
            if 'createdAt' in device[key]:
                created_at = dateutil.parser.parse(device[key]['createdAt'])
                device[key]['createdAt'] = created_at

            if 'updatedAt' in device[key]:
                updated_at = dateutil.parser.parse(device[key]['updatedAt'])
                device[key]['updatedAt'] = updated_at

        return device

    @staticmethod
    def _prepare_charger(charger):
        return BatteryTender._prepare_device(charger, 'charger')

    @staticmethod
    def _prepare_monitor(monitor):
        return BatteryTender._prepare_device(monitor, 'monitor')

    # NOTE(jkoelker) This is untested, I do not have a charger
    #                PR's welcome.
    def _charger(self, device_id):
        if device_id not in self._charger_cache.keys():
            charger = self._request('GET', CHARGER_PATH,
                                    params={'chargerId': device_id})
            self._charger_cache[device_id] = self._prepare_charger(charger)

        return self._charger_cache.get(device_id)

    def _monitor(self, device_id):
        if device_id not in self._monitor_cache.keys():
            monitor = self._request('GET', MONITOR_PATH,
                                    params={'monitorId': device_id})
            self._monitor_cache[device_id] = self._prepare_monitor(monitor)

        return self._monitor_cache.get(device_id)

    def refresh_cache(self):
        # NOTE(jkoelker) Hit login without the params to trigger
        #                initial login and callback
        self._request('POST', LOGIN_PATH)

    @property
    def chargers(self):
        # NOTE(jkoelker) This is untested, I do not have a charger
        #                PR's welcome.
        if not self._chargers_cache.keys():
            self.refresh_cache()

        return [Charger(c, self) for c in self._chargers_cache.keys()]

    @property
    def monitors(self):
        if not self._monitors_cache.keys():
            self.refresh_cache()

        return [Monitor(m, self) for m in self._monitors_cache.keys()]
