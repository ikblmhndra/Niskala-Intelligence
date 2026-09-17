import json

import structlog
from cti_core.logging import configure_logging, get_logger


def test_json_log_has_bound_context_and_required_fields(
    capsys: object,
) -> None:
    configure_logging(level="INFO", json=True)
    log = get_logger(scraper_id="gbhackers", run_id="r1")
    log.info("run_started", items_found=3)

    captured = capsys.readouterr()  # type: ignore[attr-defined]
    line = json.loads(captured.out.strip().splitlines()[-1])

    assert line["scraper_id"] == "gbhackers"
    assert line["run_id"] == "r1"
    assert line["items_found"] == 3
    assert line["event"] == "run_started"
    assert line["level"] == "info"
    assert "timestamp" in line


def test_configure_logging_is_idempotent() -> None:
    # Dipanggil beberapa kali (mis. tiap test) gak boleh numpuk processor
    # atau ngelempar exception.
    configure_logging()
    configure_logging()
    configure_logging(json=False)
    structlog.reset_defaults()
    configure_logging(json=True)
