"""Test api.py."""
import os
from unittest import TestCase
from unittest.mock import patch, MagicMock
import productionsystem.api as api


class TestJSI(TestCase):
    """Test case for api.py."""

    def test__init__(self):
        """Test JSI Instantiation."""
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

    @patch("requests.get")
    def test_get_requests(self, mock_get):
        """Test get_requests method."""
        # Testing getting all requests
        jsi = api.JSI("http://localhost:8080")
        jsi.get_requests()
        mock_get.assert_called_once_with('http://localhost:8080/api/requests', verify=False, cert=None)
        mock_get.reset_mock()

        mock_get.return_value.raise_for_status.side_effect = api.requests.exceptions.HTTPError(400)
        with self.assertRaisesRegex(api.requests.exceptions.HTTPError, "400"):
            jsi.get_requests()
        mock_get.assert_called_once_with('http://localhost:8080/api/requests', verify=False, cert=None)
        mock_get.reset_mock()

        # Testing getting single request
        with self.assertRaisesRegex(TypeError, "request_id parameter should be of type int"):
            jsi.get_requests("12")
        mock_get.return_value.raise_for_status = MagicMock()
        requests = jsi.get_requests(12)
        self.assertEqual(len(mock_get.call_args_list), 2)
        mock_get.assert_any_call('http://localhost:8080/api/requests/12', verify=False, cert=None)
        mock_get.assert_any_call('http://localhost:8080/api/requests/12/parametricjobs', verify=False, cert=None)
        self.assertIsInstance(requests, list)
        mock_get.reset_mock()

        mock_get.return_value.raise_for_status.side_effect = api.requests.exceptions.HTTPError(400)
        with self.assertRaisesRegex(api.requests.exceptions.HTTPError, "400"):
            jsi.get_requests(12)
        mock_get.assert_called_once_with('http://localhost:8080/api/requests/12', verify=False, cert=None)

    @patch("requests.post")
    def test_create_request(self, mock_post):
        """Test create_requests method."""
        jsi = api.JSI("http://localhost:8080")
        with self.assertRaisesRegex(TypeError, "request parameter should be of type dict"):
            jsi.create_request(12)
        jsi.create_request({})
        mock_post.assert_called_once_with('http://localhost:8080/api/requests', json={'request': {}}, verify=False, cert=None)
        mock_post.reset_mock()

        mock_post.return_value.raise_for_status.side_effect = api.requests.exceptions.HTTPError(400)
        with self.assertRaisesRegex(api.requests.exceptions.HTTPError, "400"):
            jsi.create_request({})
        mock_post.assert_called_once_with('http://localhost:8080/api/requests', json={'request': {}}, verify=False, cert=None)

    @patch("requests.delete")
    def test_delete_request(self, mock_delete):
        """Test delete_requests method."""
        jsi = api.JSI("http://localhost:8080")
        with self.assertRaisesRegex(TypeError, "request_id parameter should be of type int"):
            jsi.delete_request("12")
        jsi.delete_request(12)
        mock_delete.assert_called_once_with('http://localhost:8080/api/requests/12', verify=False, cert=None)
        mock_delete.reset_mock()

        mock_delete.return_value.raise_for_status.side_effect = api.requests.exceptions.HTTPError(400)
        with self.assertRaisesRegex(api.requests.exceptions.HTTPError, "400"):
            jsi.delete_request(12)
        mock_delete.assert_called_once_with('http://localhost:8080/api/requests/12', verify=False, cert=None)

    @patch("requests.put")
    def test_approve_request(self, mock_put):
        """Test approve_request method."""
        jsi = api.JSI("http://localhost:8080")
        with self.assertRaisesRegex(TypeError, "request_id parameter should be of type int"):
            jsi.approve_request("12")
        jsi.approve_request(12)
        mock_put.assert_called_once_with('http://localhost:8080/api/requests/12', data={'status': 'Approved'}, verify=False, cert=None)
        mock_put.reset_mock()

        mock_put.return_value.raise_for_status.side_effect = api.requests.exceptions.HTTPError(400)
        with self.assertRaisesRegex(api.requests.exceptions.HTTPError, "400"):
            jsi.approve_request(12)
        mock_put.assert_called_once_with('http://localhost:8080/api/requests/12', data={'status': 'Approved'}, verify=False, cert=None)


class TestLiveServer(TestCase):
    """
    Test the API against a live server.

    Note these tests require a valid x509 cert/key pair which is registered with the live server.
    Also the key file should be unencrypted and the names of the files should be usercert.pem and
    userkey-unenc.pem and be located in a .globus directory under the users home directory.
    """

    def test_get_requests(self):
        """Test get_requests method."""
        jsi = api.JSI("https://lzprod01.grid.hep.ph.ic.ac.uk:8443",
                      verify=False,
                      cert=(os.path.join(os.path.expanduser("~"), ".globus", "usercert.pem"),
                            os.path.join(os.path.expanduser("~"), ".globus", "userkey-unenc.pem")))
        self.assertIsInstance(jsi.get_requests(), list)
