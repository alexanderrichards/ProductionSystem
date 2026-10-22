"""
Test api.py.

Check JSI argument validation and outgoing HTTP calls using mocks. A separate
live-server case requires locally installed, registered X.509 credentials.
"""
import os
from unittest import TestCase
from unittest.mock import ANY, MagicMock, patch

import productionsystem.api as api


class TestJSI(TestCase):
    """
    Test case for api.py.

    Exercise client construction, request queries, lifecycle operations, and
    propagation of HTTP status errors without contacting a real server.
    """
    def test__init__(self):
        """
        Test JSI Instantiation.

        Check required and invalid arguments, accepted certificate and trust
        settings, and storage of the normalized service URL.
        """
        with self.assertRaisesRegex(TypeError, "missing 1 required positional argument: 'url'"):
            api.JSI()
        with self.assertRaisesRegex(TypeError, "Expected url to be a string"):
            api.JSI(1)
        with self.assertRaisesRegex(TypeError, "Expected cert to be"):
            api.JSI("http://localhost:8080", cert=12)
        with self.assertRaisesRegex(TypeError, "Expected verify to be"):
            api.JSI("http://localhost:8080", verify=12)

        # basic initialisation
        jsi = api.JSI("http://localhost:8080")
        self.assertEqual(jsi._url, api.up.urlsplit("http://localhost:8080"))
        self.assertEqual(jsi._cert, None)
        self.assertEqual(jsi._verify, False)
        # test verify
        api.JSI("http://localhost:8080", verify="test")
        api.JSI("http://localhost:8080", verify=True)
        api.JSI("http://localhost:8080", verify=False)
        # test cert
        api.JSI("http://localhost:8080", cert="test")
        api.JSI("http://localhost:8080", cert=("test1", "test2"))
        api.JSI("http://localhost:8080", cert=None)
        # test full initialisation
        jsi = api.JSI("http://localhost:8080", cert="test", verify=True)
        self.assertEqual(jsi._url, api.up.urlsplit("http://localhost:8080"))
        self.assertEqual(jsi._cert, "test")
        self.assertEqual(jsi._verify, True)

    @patch("httpx.Client.request", autospec=True)
    def test_get_requests(self, mock_get):
        """
        Test get_requests method.

        Check collection and individual queries, nested parametric-job fetching,
        identifier validation, and propagation of unsuccessful responses.

        Args:
            mock_get (MagicMock): Patched HTTPX request method.
        """
        # Testing getting all requests
        jsi = api.JSI("http://localhost:8080")
        jsi.get_requests()
        mock_get.assert_called_once_with(ANY, "GET", 'http://localhost:8080/api/requests')
        mock_get.reset_mock()

        mock_get.return_value.raise_for_status.side_effect = api.httpx.HTTPStatusError("400", request=MagicMock(), response=MagicMock())
        with self.assertRaisesRegex(api.httpx.HTTPStatusError, "400"):
            jsi.get_requests()
        mock_get.assert_called_once_with(ANY, "GET", 'http://localhost:8080/api/requests')
        mock_get.reset_mock()

        # Testing getting single request
        with self.assertRaisesRegex(TypeError, "request_id parameter should be of type int"):
            jsi.get_requests("12")
        mock_get.return_value.raise_for_status = MagicMock()
        requests = jsi.get_requests(12)
        self.assertEqual(len(mock_get.call_args_list), 2)
        mock_get.assert_any_call(ANY, "GET", 'http://localhost:8080/api/requests/12')
        mock_get.assert_any_call(ANY, "GET", 'http://localhost:8080/api/requests/12/parametricjobs')
        self.assertIsInstance(requests, list)
        mock_get.reset_mock()

        mock_get.return_value.raise_for_status.side_effect = api.httpx.HTTPStatusError("400", request=MagicMock(), response=MagicMock())
        with self.assertRaisesRegex(api.httpx.HTTPStatusError, "400"):
            jsi.get_requests(12)
        mock_get.assert_called_once_with(ANY, "GET", 'http://localhost:8080/api/requests/12')

    @patch("httpx.Client.request", autospec=True)
    def test_create_request(self, mock_post):
        """
        Test create_requests method.

        Check request-body wrapping, dictionary validation, and propagation of
        server errors.

        Args:
            mock_post (MagicMock): Patched HTTPX request method.
        """
        jsi = api.JSI("http://localhost:8080")
        with self.assertRaisesRegex(TypeError, "request parameter should be of type dict"):
            jsi.create_request(12)
        jsi.create_request({})
        mock_post.assert_called_once_with(ANY, "POST", 'http://localhost:8080/api/requests', json={'request': {}})
        mock_post.reset_mock()

        mock_post.return_value.raise_for_status.side_effect = api.httpx.HTTPStatusError("400", request=MagicMock(), response=MagicMock())
        with self.assertRaisesRegex(api.httpx.HTTPStatusError, "400"):
            jsi.create_request({})
        mock_post.assert_called_once_with(ANY, "POST", 'http://localhost:8080/api/requests', json={'request': {}})

    @patch("httpx.Client.request", autospec=True)
    def test_delete_request(self, mock_delete):
        """
        Test delete_requests method.

        Check the deletion endpoint, identifier validation, and propagation of
        unsuccessful responses.

        Args:
            mock_delete (MagicMock): Patched HTTPX request method.
        """
        jsi = api.JSI("http://localhost:8080")
        with self.assertRaisesRegex(TypeError, "request_id parameter should be of type int"):
            jsi.delete_request("12")
        jsi.delete_request(12)
        mock_delete.assert_called_once_with(ANY, "DELETE", 'http://localhost:8080/api/requests/12')
        mock_delete.reset_mock()

        mock_delete.return_value.raise_for_status.side_effect = api.httpx.HTTPStatusError("400", request=MagicMock(), response=MagicMock())
        with self.assertRaisesRegex(api.httpx.HTTPStatusError, "400"):
            jsi.delete_request(12)
        mock_delete.assert_called_once_with(ANY, "DELETE", 'http://localhost:8080/api/requests/12')

    @patch("httpx.Client.request", autospec=True)
    def test_approve_request(self, mock_put):
        """
        Test approve_request method.

        Check the approval form payload, identifier validation, and propagation
        of unsuccessful responses.

        Args:
            mock_put (MagicMock): Patched HTTPX request method.
        """
        jsi = api.JSI("http://localhost:8080")
        with self.assertRaisesRegex(TypeError, "request_id parameter should be of type int"):
            jsi.approve_request("12")
        jsi.approve_request(12)
        mock_put.assert_called_once_with(ANY, "PUT", 'http://localhost:8080/api/requests/12', data={'status': 'Approved'})
        mock_put.reset_mock()

        mock_put.return_value.raise_for_status.side_effect = api.httpx.HTTPStatusError("400", request=MagicMock(), response=MagicMock())
        with self.assertRaisesRegex(api.httpx.HTTPStatusError, "400"):
            jsi.approve_request(12)
        mock_put.assert_called_once_with(ANY, "PUT", 'http://localhost:8080/api/requests/12', data={'status': 'Approved'})


class TestLiveServer(TestCase):
    """
    Test the API against a live server.

    Note these tests require a valid x509 cert/key pair which is registered with the live server.
    Also the key file should be unencrypted and the names of the files should be usercert.pem and
    userkey-unenc.pem and be located in a .globus directory under the users home directory.
    """

    def test_get_requests(self):
        """
        Test get_requests method.

        Contact the configured production host with the user's certificate and
        assert that request retrieval returns a list. This is an authenticated
        network integration test, not an isolated unit test.
        """
        jsi = api.JSI("https://lzprod01.grid.hep.ph.ic.ac.uk:8443",
                      verify=False,
                      cert=(os.path.join(os.path.expanduser("~"), ".globus", "usercert.pem"),
                            os.path.join(os.path.expanduser("~"), ".globus", "userkey-unenc.pem")))
        self.assertIsInstance(jsi.get_requests(), list)
