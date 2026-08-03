import pytest
from src.improver import check_host_memory, available_host_bytes


GIB = 1024 ** 3


def test_passes_when_memory_is_sufficient():
    check_host_memory(available_bytes=18 * GIB, required_bytes=6 * GIB)


def test_passes_at_exact_boundary():
    check_host_memory(available_bytes=6 * GIB, required_bytes=6 * GIB)


def test_raises_when_memory_is_short():
    with pytest.raises(RuntimeError):
        check_host_memory(available_bytes=5 * GIB, required_bytes=6 * GIB)


def test_message_reports_both_figures_in_gib():
    with pytest.raises(RuntimeError) as exc:
        check_host_memory(available_bytes=5 * GIB, required_bytes=6 * GIB)
    msg = str(exc.value)
    assert "5.0 GiB" in msg
    assert "6.0 GiB" in msg


def test_message_names_the_other_workload_as_the_cause():
    # The failure this guards against is always caused by something else on the
    # box holding memory, so the message has to point there — otherwise it
    # reads as "the model is too big" and sends you after the wrong thing.
    with pytest.raises(RuntimeError) as exc:
        check_host_memory(available_bytes=5 * GIB, required_bytes=6 * GIB)
    assert "other processes" in str(exc.value).lower()


def test_skipped_when_availability_is_unknown():
    # available_host_bytes() returns None on a system without the expected
    # /proc/meminfo field; an unknown figure must not block loading.
    check_host_memory(available_bytes=None, required_bytes=6 * GIB)


def test_available_host_bytes_reads_a_plausible_value():
    value = available_host_bytes()
    assert value is None or value > 0
