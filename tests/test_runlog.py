"""Log lifecycle and rotation with synthetic inputs."""
import re
import logging

import pytest

from excel_consolidator import runlog
from excel_consolidator.cli import main, run_config
from excel_consolidator.config import RuntimeConfig
from excel_consolidator.errors import ConsolidationError
from excel_consolidator.quality import QualityOptions


def test_real_execution_appends(tmp_path, make_xlsx, capsys):
    folder = tmp_path / 'input'
    make_xlsx(folder / 'a.xlsx', [['A'], [1], [1]])
    log = tmp_path / 'logs' / 'run.log'
    args = ['--input', str(folder), '--output', str(tmp_path / 'out.xlsx'), '--log-file', str(log)]
    assert main(args) == 0
    first = log.read_text()
    lines = first.splitlines()
    assert len(lines) == 3
    assert all(re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} INFO ', line) for line in lines)
    assert 'start input=' in lines[0] and 'flags=none key=-' in lines[0]
    assert lines[1].endswith('read files=1 rows_read=2')
    assert 'written rows=2 nulls=0 duplicates=1 removed=0 changed=0 output=' in lines[2]
    assert main(args) == 0
    assert log.read_text().startswith(first)
    assert len(log.read_text().splitlines()) == 6
    assert not logging.getLogger(runlog.LOGGER_NAME).handlers
    assert capsys.readouterr().err == ''


def test_rotation(tmp_path, make_xlsx, monkeypatch):
    make_xlsx(tmp_path / 'input' / 'a.xlsx', [['A'], [1]])
    log = tmp_path / 'run.log'
    args = ['--input', str(tmp_path / 'input'), '--output', str(tmp_path / 'out.xlsx'), '--log-file', str(log)]
    assert main(args) == 0
    size = log.stat().st_size
    monkeypatch.setattr(runlog, 'DEFAULT_MAX_BYTES', size - 1)
    assert main(args) == 0
    assert log.with_name('run.log.1').exists()
    assert log.stat().st_size < size


def test_setup_and_close(tmp_path):
    log = tmp_path / 'nested' / 'run.log'
    logger = runlog.setup_logging(log)
    old = logger.handlers[0]
    assert logger.level == logging.INFO and logger.propagate is False
    assert runlog.setup_logging(log) is logger
    assert old.stream is None
    assert len(logger.handlers) == 1
    runlog.close_logging(logger)
    runlog.close_logging(logger)
    assert not logger.handlers
    blocker = tmp_path / 'file'
    blocker.write_text('blocked')
    with pytest.raises(ConsolidationError, match=str(blocker)):
        runlog.setup_logging(blocker / 'run.log')


def test_importable_run_config_is_silent(tmp_path, make_xlsx, capsys):
    make_xlsx(tmp_path / 'input' / 'a.xlsx', [['A'], [1]])
    config = RuntimeConfig(tmp_path / 'input', tmp_path / 'out.xlsx', tmp_path / 'unused.log', QualityOptions())
    assert run_config(config).rows == 1
    assert not config.log_file.exists()
    captured = capsys.readouterr()
    assert captured.out == captured.err == ''
