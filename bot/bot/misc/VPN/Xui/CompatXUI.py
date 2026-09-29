import logging
import re
from typing import Any, Dict, Optional, Union

import aiohttp
from pyxui_async import XUI
from pyxui_async.errors import AlreadyLogin, BadLogin, NotFound
from pyxui_async.models import POST, ResponseBase


class CompatXUI(XUI):
    additional_inbound_ids: list[int]

    async def open(self):
        if self._session is None or self._closed:
            self._session = aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar(unsafe=True)
            )
            self._closed = False

    async def login(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Union[ResponseBase, BadLogin, AlreadyLogin]:
        if self._session is not None and not self._closed:
            raise AlreadyLogin()
        data = {
            'username': username or self.username,
            'password': password or self.password,
            'twoFactorCode': '',
        }
        result = await self.request(method=POST, endpoint='/login', data=data)
        if result.get('success', False):
            return ResponseBase(**result)
        raise BadLogin()

    def _cookie_header(self) -> str:
        return '; '.join(f'{key}={value}' for key, value in self.cookies.items())

    def _remember_response_cookies(self, response: aiohttp.ClientResponse) -> None:
        for cookie in response.cookies.values():
            self.cookies[cookie.key] = cookie.value

    async def _get_csrf_token(self) -> str:
        csrf_token = getattr(self, '_csrf_token', None)
        if csrf_token:
            return csrf_token
        await self.open()
        headers = {'X-Requested-With': 'XMLHttpRequest'}
        if self.cookies:
            headers['Cookie'] = self._cookie_header()
        async with self._session.get(
            f'{self.address}/csrf-token',
            headers=headers,
            timeout=self.timeout,
            ssl=self.https,
        ) as response:
            self._remember_response_cookies(response)
            result = await _verify_response(response)
        token = None
        if isinstance(result, dict):
            token = (
                result.get('csrf_token')
                or result.get('csrfToken')
                or result.get('obj')
            )
        if not token:
            raise ValueError('CSRF token is missing in 3x-ui response')
        self._csrf_token = token
        return token

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        json: Any = None,
        data: Any = None,
        params: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
    ) -> Union[dict, bytes, str, NotFound]:
        await self.open()
        url = f'{self.address}{endpoint}'
        try:
            request_headers = {'X-Requested-With': 'XMLHttpRequest'}
            if headers:
                request_headers.update(headers)
            if method.upper() in {'POST', 'PUT', 'PATCH', 'DELETE'}:
                request_headers.setdefault(
                    'X-CSRF-Token',
                    await self._get_csrf_token(),
                )
            if self.cookies:
                request_headers['Cookie'] = self._cookie_header()
            async with self._session.request(
                method,
                url,
                json=json,
                data=data,
                params=params,
                headers=request_headers,
                timeout=self.timeout,
                ssl=self.https,
            ) as response:
                self._remember_response_cookies(response)
                return await _verify_response(response)
        except Exception as err:
            logging.error(err)
            raise
        finally:
            await self.close()

    def get_domain(self) -> Union[str, ValueError]:
        pattern = r'^(?:https?://)?([a-zA-Z0-9.-]+)(?::\d+)?(?:/.*)?$'
        match = re.match(pattern, self.address)
        if match:
            return match.group(1)
        raise ValueError('Invalid URL server')

    async def add_clients(self, inbound_id, client_settings):
        inbound_ids = list(
            dict.fromkeys(
                [int(inbound_id)]
                + [int(value) for value in getattr(self, 'additional_inbound_ids', [])]
            )
        )
        for client in client_settings.clients:
            payload = client.model_dump(exclude_none=True)
            payload['security'] = payload.get('security') or 'auto'
            # pyxui emits tgId='' whereas the global API expects a number.
            payload['tgId'] = int(payload.get('tgId') or 0)
            result = await self.request(
                method=POST,
                endpoint='/panel/api/clients/add',
                json={'client': payload, 'inboundIds': inbound_ids},
            )
            if not isinstance(result, dict) or not result.get('success'):
                message = (
                    result.get('msg', 'Failed to add global XUI client')
                    if isinstance(result, dict)
                    else 'Unexpected response while adding global XUI client'
                )
                return ResponseBase(
                    success=False,
                    msg=message,
                )
        return ResponseBase(success=True, msg='Client added')


async def _verify_response(
    response: aiohttp.ClientResponse,
) -> Union[dict, bytes, str]:
    content_type = response.headers.get('Content-Type', '')
    if response.status == 404:
        raise NotFound()
    if not (200 <= response.status < 300):
        try:
            error_text = await response.text()
            raise ValueError(f'HTTP {response.status}: {error_text}')
        except UnicodeDecodeError:
            raise ValueError(
                f'HTTP {response.status}: Binary response with an error'
            )
    if content_type.startswith('application/json'):
        return await response.json()
    if content_type.startswith(
        ('text/plain', 'text/html', 'text/css', 'text/javascript', 'text/xml')
    ):
        return await response.text()
    return await response.read()
