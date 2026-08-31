"""The launcher: the shell line it builds, and the sentinel file it waits on.

Nothing here opens a window. osascript is never run -- the two calls that would
are patched -- so the suite is the same on a machine with no Terminal.app.
"""

import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from terminalgame.app import launcher
from terminalgame.app.launcher import LaunchError


class SupportTest(unittest.TestCase):

    def test_a_mac_with_osascript_can_be_driven(self):
        with mock.patch.object(launcher.sys, "platform", "darwin"), \
                mock.patch.object(launcher.os.path, "exists", return_value=True):
            self.assertTrue(launcher.is_supported())

    def test_another_platform_cannot(self):
        with mock.patch.object(launcher.sys, "platform", "linux"):
            self.assertFalse(launcher.is_supported())

    def test_a_mac_without_osascript_cannot(self):
        with mock.patch.object(launcher.sys, "platform", "darwin"), \
                mock.patch.object(launcher.os.path, "exists", return_value=False):
            self.assertFalse(launcher.is_supported())


class SentinelTest(unittest.TestCase):
    """The child's half and the launcher's half, tested against each other."""

    def setUp(self):
        directory = tempfile.mkdtemp(prefix="terminalgame-test-")
        self.addCleanup(self.remove, directory)
        self.sentinel = os.path.join(directory, "sentinel")
        self.directory = directory

    def remove(self, directory):
        for name in os.listdir(directory):
            os.unlink(os.path.join(directory, name))
        os.rmdir(directory)

    def test_a_started_child_is_read_back_as_its_pid(self):
        launcher.announce_started(self.sentinel)

        self.assertEqual(("pid", os.getpid()), launcher._read_sentinel(self.sentinel))

    def test_a_finished_child_is_read_back_as_its_exit_code(self):
        launcher.announce_finished(self.sentinel, 1)

        self.assertEqual(("exit", 1), launcher._read_sentinel(self.sentinel))

    def test_finishing_replaces_the_pid_that_was_there(self):
        launcher.announce_started(self.sentinel)
        launcher.announce_finished(self.sentinel, 0)

        self.assertEqual(("exit", 0), launcher._read_sentinel(self.sentinel))

    def test_no_temporary_file_is_left_behind(self):
        """It is renamed into place, so the launcher never reads a half-written one."""
        launcher.announce_started(self.sentinel)

        self.assertFalse(os.path.exists(self.sentinel + ".tmp"))

    def test_a_sentinel_that_is_not_there_yet_reads_as_nothing(self):
        self.assertEqual((None, 0), launcher._read_sentinel(self.sentinel))

    def test_a_sentinel_holding_nonsense_reads_as_nothing(self):
        with open(self.sentinel, "w") as handle:
            handle.write("half a li")

        self.assertEqual((None, 0), launcher._read_sentinel(self.sentinel))

    def test_a_child_with_nobody_watching_writes_no_file(self):
        launcher.announce_started(None)
        launcher.announce_finished(None, 0)

        self.assertEqual([], os.listdir(self.directory))

    def test_an_unwritable_sentinel_does_not_bring_the_game_down(self):
        """The launcher's liveness check covers a sentinel that never arrives."""
        launcher.announce_finished(os.path.join(self.directory, "no", "such", "dir"), 0)

    def test_cleanup_takes_the_directory_with_it(self):
        launcher.announce_started(self.sentinel)

        launcher._cleanup(self.directory, self.sentinel)

        self.assertFalse(os.path.exists(self.directory))
        os.mkdir(self.directory)  # put it back for the cleanup hook

    def test_cleanup_of_something_already_gone_is_harmless(self):
        launcher._cleanup(self.directory, self.sentinel)
        launcher._cleanup(self.directory, self.sentinel)
        os.mkdir(self.directory)


class CommandTest(unittest.TestCase):
    """The shell line Terminal is asked to run in the new window."""

    def test_the_child_runs_the_game_as_a_module(self):
        command = launcher._build_command("/tmp/s", [])

        self.assertIn("-m {}".format(launcher.MAIN_MODULE), command)

    def test_the_child_runs_the_same_interpreter_as_the_launcher(self):
        command = launcher._build_command("/tmp/s", [])

        self.assertIn(shlex.quote(sys.executable), command)

    def test_the_shell_starts_in_the_project_root_so_the_import_resolves(self):
        command = launcher._build_command("/tmp/s", [])

        self.assertTrue(command.startswith("cd " + shlex.quote(launcher._project_root())))

    def test_python_replaces_the_shell_so_the_tab_closes_on_its_own(self):
        self.assertIn("exec", launcher._build_command("/tmp/s", []).split())

    def test_the_child_is_told_its_role_through_the_environment(self):
        """Not through argv, which Terminal would put in the window title."""
        command = launcher._build_command("/tmp/s", [])

        self.assertIn("{}=1".format(launcher.ENV_CHILD), command)
        self.assertIn("{}=/tmp/s".format(launcher.ENV_SENTINEL), command)

    def test_a_sentinel_path_with_spaces_is_quoted_for_the_shell(self):
        command = launcher._build_command("/tmp/a game/sentinel", [])

        self.assertIn("{}={}".format(launcher.ENV_SENTINEL,
                                     shlex.quote("/tmp/a game/sentinel")), command)
        self.assertNotIn("=/tmp/a game/sentinel ", command)

    def test_extra_arguments_are_passed_on_and_quoted(self):
        command = launcher._build_command("/tmp/s", ["--flag", "two words"])

        self.assertTrue(command.endswith("--flag {}".format(shlex.quote("two words"))))

    def test_the_project_root_is_the_directory_holding_the_package(self):
        """Derived from this file, since argv[0] under -m points inside the package."""
        root = launcher._project_root()

        self.assertTrue(os.path.isdir(os.path.join(root, "terminalgame")))
        self.assertTrue(os.path.isfile(os.path.join(root, "terminalgame", "__init__.py")))


class SpawnTest(unittest.TestCase):
    """What comes back from osascript, without osascript being run."""

    def spawn(self, stdout="", error=None):
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout)
        with mock.patch.object(launcher.subprocess, "run",
                               side_effect=error, return_value=completed) as run:
            return launcher._spawn_window("cd /tmp && echo hi", 30, 40), run

    def test_the_window_id_comes_back_as_a_number(self):
        window_id, _ = self.spawn(stdout="12345\n")

        self.assertEqual(12345, window_id)

    def test_a_window_that_cannot_be_identified_is_simply_never_closed(self):
        window_id, _ = self.spawn(stdout="missing value\n")

        self.assertEqual(0, window_id)

    def test_the_playfield_size_reaches_the_script(self):
        _, run = self.spawn(stdout="1")
        script = run.call_args[0][0][-1]

        self.assertIn("set number of rows of gameTab to 30", script)
        self.assertIn("set number of columns of gameTab to 40", script)

    def test_the_window_gets_a_title_instead_of_the_command_line(self):
        _, run = self.spawn(stdout="1")
        script = run.call_args[0][0][-1]

        self.assertIn(launcher.WINDOW_TITLE, script)

    def test_quotes_in_the_command_survive_being_put_inside_the_script(self):
        """The command is embedded in an AppleScript string literal."""
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="1")
        with mock.patch.object(launcher.subprocess, "run", return_value=completed) as run:
            launcher._spawn_window('echo "hi" \\ there', 30, 40)
        script = run.call_args[0][0][-1]

        self.assertIn('echo \\"hi\\" \\\\ there', script)

    def test_a_terminal_that_refuses_is_reported_as_a_launch_error(self):
        failure = subprocess.CalledProcessError(1, "osascript", stderr="not allowed")

        with self.assertRaises(LaunchError) as caught:
            self.spawn(error=failure)

        self.assertIn("not allowed", str(caught.exception))


class ProcessLivenessTest(unittest.TestCase):

    def test_this_very_process_is_alive(self):
        self.assertTrue(launcher._process_alive(os.getpid()))

    def test_a_process_that_has_gone_is_not(self):
        with mock.patch.object(launcher.os, "kill", side_effect=ProcessLookupError):
            self.assertFalse(launcher._process_alive(1))

    def test_a_process_owned_by_somebody_else_counts_as_alive(self):
        """The signal being refused is itself proof the process exists."""
        with mock.patch.object(launcher.os, "kill", side_effect=PermissionError):
            self.assertTrue(launcher._process_alive(1))


class WaitTest(unittest.TestCase):
    """Waiting on the child, with the sentinel written by hand."""

    def setUp(self):
        directory = tempfile.mkdtemp(prefix="terminalgame-test-")
        self.sentinel = os.path.join(directory, "sentinel")
        self.addCleanup(launcher._cleanup, directory, self.sentinel)

    def write(self, text):
        with open(self.sentinel, "w") as handle:
            handle.write(text)

    def test_an_exit_code_is_handed_straight_back(self):
        self.write("exit 3")

        self.assertEqual((3, None), launcher._wait_for_child(self.sentinel))

    def test_the_pid_comes_back_with_the_exit_code_so_the_window_can_wait(self):
        """The window must not be closed while the process is still unwinding."""
        self.write("pid {}".format(os.getpid()))
        states = [("pid", os.getpid()), ("exit", 0)]

        with mock.patch.object(launcher, "_read_sentinel", side_effect=states), \
                mock.patch.object(launcher.time, "sleep"):
            self.assertEqual((0, os.getpid()), launcher._wait_for_child(self.sentinel))

    def test_a_window_closed_from_under_the_game_ends_the_wait(self):
        """No exit code was ever written, so the launcher checks the process instead."""
        self.write("pid 424242")

        with mock.patch.object(launcher, "_process_alive", return_value=False), \
                mock.patch.object(launcher.time, "sleep"):
            self.assertEqual((0, None), launcher._wait_for_child(self.sentinel))

    def test_a_child_that_never_starts_gives_up_rather_than_waiting_forever(self):
        with mock.patch.object(launcher, "STARTUP_TIMEOUT_SECONDS", -1), \
                mock.patch.object(launcher.time, "sleep"):
            with self.assertRaises(LaunchError) as caught:
                launcher._wait_for_child(self.sentinel)

        self.assertIn("did not start", str(caught.exception))

    def test_waiting_for_a_process_to_leave_gives_up_after_its_timeout(self):
        slept = []
        with mock.patch.object(launcher, "_process_alive", return_value=True), \
                mock.patch.object(launcher.time, "sleep", slept.append), \
                mock.patch.object(launcher, "CHILD_EXIT_TIMEOUT_SECONDS", 0.05):
            launcher._wait_for_process_exit(os.getpid())

        self.assertTrue(slept, "it never waited at all")

    def test_waiting_for_a_process_that_has_already_gone_returns_at_once(self):
        slept = []
        with mock.patch.object(launcher, "_process_alive", return_value=False), \
                mock.patch.object(launcher.time, "sleep", slept.append):
            launcher._wait_for_process_exit(1)

        self.assertEqual([], slept)


class LaunchTest(unittest.TestCase):
    """The whole spawn-and-wait, with the two osascript calls held back."""

    def test_the_child_is_refused_a_window_of_its_own(self):
        """Each generation would open a real window, so recursion is refused outright."""
        with mock.patch.dict(os.environ, {launcher.ENV_CHILD: "1"}):
            with self.assertRaises(LaunchError) as caught:
                launcher.launch(30, 40, [])

        self.assertIn(launcher.ENV_CHILD, str(caught.exception))

    def test_a_platform_that_cannot_drive_terminal_says_to_use_here_instead(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(launcher, "is_supported", return_value=False):
            with self.assertRaises(LaunchError) as caught:
                launcher.launch(30, 40, [])

        self.assertIn("--here", str(caught.exception))

    def test_the_game_s_exit_code_is_forwarded_to_whoever_ran_the_command(self):
        with self.launching(exit_code=2) as calls:
            self.assertEqual(2, launcher.launch(30, 40, []))
        self.assertEqual([("spawn",), ("close", 99)], calls)

    def test_the_window_is_closed_once_the_game_has_finished(self):
        with self.launching(exit_code=0) as calls:
            launcher.launch(30, 40, [])

        self.assertIn(("close", 99), calls)

    def test_a_window_that_was_never_identified_is_not_closed(self):
        with self.launching(exit_code=0, window_id=0) as calls:
            launcher.launch(30, 40, [])

        self.assertEqual([("spawn",)], calls)

    def test_the_temporary_directory_is_cleaned_up_even_when_spawning_fails(self):
        directories = []
        real_mkdtemp = launcher.tempfile.mkdtemp

        def record(**kwargs):
            directories.append(real_mkdtemp(**kwargs))
            return directories[-1]

        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(launcher, "is_supported", return_value=True), \
                mock.patch.object(launcher.tempfile, "mkdtemp", record), \
                mock.patch.object(launcher, "_spawn_window",
                                  side_effect=LaunchError("refused")):
            with self.assertRaises(LaunchError):
                launcher.launch(30, 40, [])

        self.assertEqual(1, len(directories))
        self.assertFalse(os.path.exists(directories[0]), "the temporary directory was left")

    def launching(self, exit_code, window_id=99):
        """Runs `launch` with the two osascript calls replaced by recordings."""
        calls = []

        class Recorder:
            def __enter__(inner):
                inner.patchers = [
                    mock.patch.dict(os.environ, {}, clear=True),
                    mock.patch.object(launcher, "is_supported", return_value=True),
                    mock.patch.object(
                        launcher, "_spawn_window",
                        side_effect=lambda *a: (calls.append(("spawn",)), window_id)[1]),
                    mock.patch.object(launcher, "_wait_for_child",
                                      return_value=(exit_code, None)),
                    mock.patch.object(
                        launcher, "_close_window",
                        side_effect=lambda i: calls.append(("close", i))),
                ]
                for patcher in inner.patchers:
                    patcher.start()
                return calls

            def __exit__(inner, *exception):
                for patcher in reversed(inner.patchers):
                    patcher.stop()
                return False

        return Recorder()


if __name__ == "__main__":
    unittest.main()
