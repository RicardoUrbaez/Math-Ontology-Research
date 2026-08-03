import argparse
import unittest
from unittest.mock import Mock, patch

from scripts import start_mathontospeak


class MathOntoSpeakLauncherTests(unittest.TestCase):
    def test_launcher_defines_the_complete_local_stack(self):
        services = start_mathontospeak.service_definitions()

        self.assertEqual([service.name for service in services], ["ONTOLOGY", "API", "WEB"])
        self.assertEqual([service.port for service in services], [3030, 8000, 5173])
        self.assertIn("uvicorn", services[1].command)
        self.assertIn("dev", services[2].command)

    def test_launcher_reuses_services_that_are_already_running(self):
        args = argparse.Namespace(
            check=False,
            no_browser=True,
            skip_fuseki=False,
            monitor_once=True,
        )

        with (
            patch("scripts.start_mathontospeak.validate_installation", return_value=[]),
            patch("scripts.start_mathontospeak.port_is_open", return_value=True),
            patch("scripts.start_mathontospeak.start_service") as start_service,
        ):
            exit_code = start_mathontospeak.run(args)

        self.assertEqual(exit_code, 0)
        start_service.assert_not_called()

    def test_launcher_restarts_fuseki_when_its_port_disappears(self):
        ontology = start_mathontospeak.service_definitions()[0]
        args = argparse.Namespace(
            check=False,
            no_browser=True,
            skip_fuseki=False,
            monitor_once=True,
        )
        restarted_process = Mock()
        restarted_process.poll.return_value = None

        with (
            patch("scripts.start_mathontospeak.service_definitions", return_value=[ontology]),
            patch("scripts.start_mathontospeak.validate_installation", return_value=[]),
            patch("scripts.start_mathontospeak.port_is_open", side_effect=[True, False]),
            patch("scripts.start_mathontospeak.start_service", return_value=restarted_process) as start_service,
            patch("scripts.start_mathontospeak.wait_until_ready", return_value=True),
            patch("scripts.start_mathontospeak.stop_process_tree") as stop_process_tree,
        ):
            exit_code = start_mathontospeak.run(args)

        self.assertEqual(exit_code, 0)
        start_service.assert_called_once_with(ontology, unittest.mock.ANY)
        stop_process_tree.assert_called_once_with(restarted_process)


if __name__ == "__main__":
    unittest.main()
