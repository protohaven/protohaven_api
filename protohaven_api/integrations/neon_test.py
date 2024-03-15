"""Tests for NeonOne integration methods"""
import datetime

from protohaven_api.integrations import neon

TEST_USER = 1234
NOW = datetime.datetime.now()
NOWSTR = NOW.strftime("%Y-%m-%d")
OLDSTR = (NOW - datetime.timedelta(days=90)).strftime("%Y-%m-%d")


def test_update_waiver_status_no_data(mocker):
    """When given no existing waiver data for the user, only return
    true if the user has just acknowledged the waiver"""
    m = mocker.patch.object(neon, "set_waiver_status")
    assert neon.update_waiver_status(TEST_USER, None, False) is False
    m.assert_not_called()  # No mutation

    # Acknowledgement triggers update
    assert neon.update_waiver_status(TEST_USER, None, True) is True
    m.assert_called()


def test_update_waiver_status_checks_version(mocker):
    """update_waiver_status returns false if the most recent signed
    version of the waiver is not the current version hosted by the server"""
    m = mocker.patch.object(neon, "set_waiver_status")
    args = [TEST_USER, False]
    kwargs = {"now": NOW, "current_version": NOWSTR}
    assert (
        neon.update_waiver_status(
            args[0], f"version {OLDSTR} on {NOWSTR}", args[1], **kwargs
        )
        is False
    )
    assert (
        neon.update_waiver_status(
            args[0], f"version {NOWSTR} on {NOWSTR}", args[1], **kwargs
        )
        is True
    )
    m.assert_not_called()  # No mutation

    # Acknowledgement triggers update
    assert (
        neon.update_waiver_status(
            args[0], f"version {OLDSTR} on {NOWSTR}", True, **kwargs
        )
        is True
    )
    m.assert_called()


def test_update_waiver_status_checks_expiration(mocker):
    """update_waiver_status returns false if the most recent signed
    waiver data of the user is older than `expiration_days`"""
    m = mocker.patch.object(neon, "set_waiver_status")
    args = [TEST_USER, f"version {OLDSTR} on {OLDSTR}", False]
    kwargs = {"now": NOW, "current_version": OLDSTR}

    assert neon.update_waiver_status(*args, **kwargs, expiration_days=1000) is True
    assert neon.update_waiver_status(*args, **kwargs, expiration_days=30) is False
    m.assert_not_called()  # No mutation

    # Acknowledgement triggers update
    args[-1] = True
    assert neon.update_waiver_status(*args, **kwargs, expiration_days=30) is True
    m.assert_called()
