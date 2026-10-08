from decimal import Decimal
from unittest.mock import patch

import pytest

from app.calculator_repl import calculator_repl
from app.exceptions import OperationError, ValidationError


@pytest.fixture
def calc():
    """Patch Calculator and the observers so the REPL runs against a mock."""
    with patch("app.calculator_repl.Calculator") as calc_cls, \
         patch("app.calculator_repl.LoggingObserver"), \
         patch("app.calculator_repl.AutoSaveObserver"):
        yield calc_cls.return_value


def run_repl(inputs):
    """Run the REPL with a scripted list of inputs."""
    with patch("builtins.input", side_effect=inputs):
        calculator_repl()


def test_startup_registers_observers_and_exit(calc, capsys):
    run_repl(["exit"])
    out = capsys.readouterr().out
    assert "Calculator started" in out
    assert "History saved successfully." in out
    assert "Goodbye!" in out
    assert calc.add_observer.call_count == 2
    calc.save_history.assert_called_once()


def test_help(calc, capsys):
    run_repl(["help", "exit"])
    out = capsys.readouterr().out
    assert "Available commands" in out
    assert "undo" in out


def test_exit_save_failure(calc, capsys):
    calc.save_history.side_effect = Exception("disk full")
    run_repl(["exit"])
    out = capsys.readouterr().out
    assert "Warning: Could not save history: disk full" in out
    assert "Goodbye!" in out


def test_history_empty(calc, capsys):
    calc.show_history.return_value = []
    run_repl(["history", "exit"])
    assert "No calculations in history" in capsys.readouterr().out


def test_history_with_entries(calc, capsys):
    calc.show_history.return_value = ["Addition(2, 3) = 5", "Power(2, 3) = 8"]
    run_repl(["history", "exit"])
    out = capsys.readouterr().out
    assert "Calculation History:" in out
    assert "1. Addition(2, 3) = 5" in out
    assert "2. Power(2, 3) = 8" in out


def test_clear(calc, capsys):
    run_repl(["clear", "exit"])
    calc.clear_history.assert_called_once()
    assert "History cleared" in capsys.readouterr().out


@pytest.mark.parametrize("returned, message", [
    (True, "Operation undone"),
    (False, "Nothing to undo"),
])
def test_undo(calc, capsys, returned, message):
    calc.undo.return_value = returned
    run_repl(["undo", "exit"])
    assert message in capsys.readouterr().out


@pytest.mark.parametrize("returned, message", [
    (True, "Operation redone"),
    (False, "Nothing to redo"),
])
def test_redo(calc, capsys, returned, message):
    calc.redo.return_value = returned
    run_repl(["redo", "exit"])
    assert message in capsys.readouterr().out


def test_save_success(calc, capsys):
    run_repl(["save", "exit"])
    assert "History saved successfully\n" in capsys.readouterr().out


def test_save_error(calc, capsys):
    calc.save_history.side_effect = Exception("no permission")
    run_repl(["save", "exit"])
    assert "Error saving history: no permission" in capsys.readouterr().out


def test_load_success(calc, capsys):
    run_repl(["load", "exit"])
    calc.load_history.assert_called_once()
    assert "History loaded successfully" in capsys.readouterr().out


def test_load_error(calc, capsys):
    calc.load_history.side_effect = Exception("file missing")
    run_repl(["load", "exit"])
    assert "Error loading history: file missing" in capsys.readouterr().out


def test_operation_decimal_result_is_normalized(calc, capsys):
    calc.perform_operation.return_value = Decimal("5.000")
    run_repl(["add", "2", "3", "exit"])
    out = capsys.readouterr().out
    assert "Result: 5\n" in out
    calc.set_operation.assert_called_once()
    calc.perform_operation.assert_called_once_with("2", "3")


def test_operation_non_decimal_result(calc, capsys):
    calc.perform_operation.return_value = 8
    run_repl(["power", "2", "3", "exit"])
    assert "Result: 8" in capsys.readouterr().out


def test_operation_cancel_first_number(calc, capsys):
    run_repl(["add", "CANCEL", "exit"])
    assert "Operation cancelled" in capsys.readouterr().out
    calc.perform_operation.assert_not_called()


def test_operation_cancel_second_number(calc, capsys):
    run_repl(["subtract", "5", "cancel", "exit"])
    assert "Operation cancelled" in capsys.readouterr().out
    calc.perform_operation.assert_not_called()


def test_operation_validation_error(calc, capsys):
    calc.perform_operation.side_effect = ValidationError("Invalid number")
    run_repl(["divide", "x", "2", "exit"])
    assert "Error: Invalid number" in capsys.readouterr().out


def test_operation_operation_error(calc, capsys):
    calc.perform_operation.side_effect = OperationError("Division by zero")
    run_repl(["divide", "1", "0", "exit"])
    assert "Error: Division by zero" in capsys.readouterr().out


def test_operation_unexpected_error(calc, capsys):
    calc.perform_operation.side_effect = RuntimeError("kaboom")
    run_repl(["multiply", "1", "2", "exit"])
    assert "Unexpected error: kaboom" in capsys.readouterr().out


def test_unknown_command(calc, capsys):
    run_repl(["foobar", "exit"])
    assert "Unknown command: 'foobar'" in capsys.readouterr().out


def test_command_is_case_insensitive_and_stripped(calc, capsys):
    run_repl(["  HELP  ", "exit"])
    assert "Available commands" in capsys.readouterr().out


def test_keyboard_interrupt(calc, capsys):
    run_repl([KeyboardInterrupt, "exit"])
    assert "Operation cancelled" in capsys.readouterr().out


def test_eof_error_exits_loop(calc, capsys):
    run_repl([EOFError])
    assert "Input terminated. Exiting..." in capsys.readouterr().out


def test_unexpected_loop_error(calc, capsys):
    run_repl([RuntimeError("boom"), "exit"])
    assert "Error: boom" in capsys.readouterr().out


def test_fatal_initialization_error(capsys):
    with patch("app.calculator_repl.Calculator", side_effect=Exception("init failed")), \
         patch("app.calculator_repl.logging.error") as log_error:
        with pytest.raises(Exception, match="init failed"):
            calculator_repl()
    assert "Fatal error: init failed" in capsys.readouterr().out
    log_error.assert_called_once()