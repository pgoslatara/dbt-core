import os
import sys
from collections import defaultdict
from unittest import mock

import pytest
import yaml
from pytest_mock import MockerFixture

import dbt_common
from dbt import deprecations
from dbt.cli.main import dbtRunner
from dbt.clients.registry import _get_cached
from dbt.events.types import (
    ArgumentsPropertyInGenericTestDeprecation,
    CustomKeyInConfigDeprecation,
    CustomKeyInObjectDeprecation,
    CustomOutputPathInSourceFreshnessDeprecation,
    DeprecationsSummary,
    DuplicateYAMLKeysDeprecation,
    EnvironmentVariableNamespaceDeprecation,
    GenericJSONSchemaValidationDeprecation,
    MissingArgumentsPropertyInGenericTestDeprecation,
    MissingPlusPrefixDeprecation,
    ModelParamUsageDeprecation,
    ModulesItertoolsUsageDeprecation,
    PackageRedirectDeprecation,
    WEOIncludeExcludeDeprecation,
)
from dbt.tests.util import read_file, run_dbt, run_dbt_and_capture, write_file
from dbt_common.events.types import Note
from dbt_common.exceptions import EventCompilationError
from tests.functional.deprecations.fixtures import (
    bad_name_yaml,
    custom_key_in_config_yaml,
    custom_key_in_object_yaml,
    deprecated_model_exposure_yaml,
    duplicate_keys_yaml,
    invalid_deprecation_date_yaml,
    models_trivial__model_sql,
    multiple_custom_keys_in_config_yaml,
    test_missing_arguments_property_yaml,
    test_with_arguments_yaml,
)
from tests.utils import EventCatcher


class TestConfigPathDeprecation:
    @pytest.fixture(scope="class")
    def models(self):
        return {"already_exists.sql": models_trivial__model_sql}

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {
            "config-version": 2,
            "data-paths": ["data"],
            "log-path": "customlogs",
            "target-path": "customtarget",
        }

    def test_data_path(self, project):
        deprecations.reset_deprecations()
        assert deprecations.active_deprecations == defaultdict(int)
        run_dbt(["debug"])
        expected = {
            "project-config-data-paths",
            "project-config-log-path",
            "project-config-target-path",
        }
        for deprecation in expected:
            assert deprecation in deprecations.active_deprecations

    def test_data_path_fail(self, project):
        deprecations.reset_deprecations()
        assert deprecations.active_deprecations == defaultdict(int)
        with pytest.raises(dbt_common.exceptions.CompilationError) as exc:
            run_dbt(["--warn-error", "debug"])
        exc_str = " ".join(str(exc.value).split())  # flatten all whitespace
        expected_msg = "The `data-paths` config has been renamed"
        assert expected_msg in exc_str


class TestPackageInstallPathDeprecation:
    @pytest.fixture(scope="class")
    def models_trivial(self):
        return {"model.sql": models_trivial__model_sql}

    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"config-version": 2, "clean-targets": ["dbt_modules"]}

    def test_package_path(self, project):
        deprecations.reset_deprecations()
        assert deprecations.active_deprecations == defaultdict(int)
        run_dbt(["clean"])
        assert "install-packages-path" in deprecations.active_deprecations

    def test_package_path_not_set(self, project):
        deprecations.reset_deprecations()
        assert deprecations.active_deprecations == defaultdict(int)
        with pytest.raises(dbt_common.exceptions.CompilationError) as exc:
            run_dbt(["--warn-error", "clean"])
        exc_str = " ".join(str(exc.value).split())  # flatten all whitespace
        expected_msg = "path has changed from `dbt_modules` to `dbt_packages`."
        assert expected_msg in exc_str


class TestPackageRedirectDeprecation:
    @pytest.fixture(scope="class")
    def models(self):
        return {"already_exists.sql": models_trivial__model_sql}

    @pytest.fixture(scope="class")
    def packages(self):
        return {"packages": [{"package": "fishtown-analytics/dbt_utils", "version": "0.7.0"}]}

    def test_package_redirect(self, project):
        deprecations.reset_deprecations()
        assert deprecations.active_deprecations == defaultdict(int)
        run_dbt(["deps"])
        assert "package-redirect" in deprecations.active_deprecations

    # if this test comes before test_package_redirect it will raise an exception as expected
    def test_package_redirect_fail(self, project):
        deprecations.reset_deprecations()
        assert deprecations.active_deprecations == defaultdict(int)
        with pytest.raises(dbt_common.exceptions.CompilationError) as exc:
            run_dbt(["--warn-error", "deps"])
        exc_str = " ".join(str(exc.value).split())  # flatten all whitespace
        expected_msg = "The `fishtown-analytics/dbt_utils` package is deprecated in favor of `dbt-labs/dbt_utils`"
        assert expected_msg in exc_str


class TestDeprecatedModelExposure:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "model.sql": models_trivial__model_sql,
            "exposure.yml": deprecated_model_exposure_yaml,
        }

    def test_exposure_with_deprecated_model(self, project):
        run_dbt(["parse"])


class TestExposureNameDeprecation:
    @pytest.fixture(scope="class")
    def models(self):
        return {"model.sql": models_trivial__model_sql, "bad_name.yml": bad_name_yaml}

    def test_exposure_name(self, project):
        deprecations.reset_deprecations()
        assert deprecations.active_deprecations == defaultdict(int)
        run_dbt(["parse"])
        assert "exposure-name" in deprecations.active_deprecations

    def test_exposure_name_fail(self, project):
        deprecations.reset_deprecations()
        assert deprecations.active_deprecations == defaultdict(int)
        with pytest.raises(dbt_common.exceptions.CompilationError) as exc:
            run_dbt(["--warn-error", "--no-partial-parse", "parse"])
        exc_str = " ".join(str(exc.value).split())  # flatten all whitespace
        expected_msg = "Starting in v1.3, the 'name' of an exposure should contain only letters, numbers, and underscores."
        assert expected_msg in exc_str


class TestProjectFlagsMovedDeprecation:
    @pytest.fixture(scope="class")
    def profiles_config_update(self):
        return {
            "config": {"send_anonymous_usage_stats": False},
        }

    @pytest.fixture(scope="class")
    def dbt_project_yml(self, project_root, project_config_update):
        project_config = {
            "name": "test",
            "profile": "test",
        }
        write_file(yaml.safe_dump(project_config), project_root, "dbt_project.yml")
        return project_config

    @pytest.fixture(scope="class")
    def models(self):
        return {"my_model.sql": "select 1 as fun"}

    def test_profile_config_deprecation(self, project):
        deprecations.reset_deprecations()
        assert deprecations.active_deprecations == defaultdict(int)

        _, logs = run_dbt_and_capture(["parse"])

        assert (
            "User config should be moved from the 'config' key in profiles.yml to the 'flags' key in dbt_project.yml."
            in logs
        )
        assert "project-flags-moved" in deprecations.active_deprecations


class TestProjectFlagsMovedDeprecationQuiet(TestProjectFlagsMovedDeprecation):
    def test_profile_config_deprecation(self, project):
        deprecations.reset_deprecations()
        assert deprecations.active_deprecations == defaultdict(int)

        _, logs = run_dbt_and_capture(["--quiet", "parse"])

        assert (
            "User config should be moved from the 'config' key in profiles.yml to the 'flags' key in dbt_project.yml."
            not in logs
        )
        assert "project-flags-moved" in deprecations.active_deprecations


class TestProjectFlagsMovedDeprecationWarnErrorOptions(TestProjectFlagsMovedDeprecation):
    def test_profile_config_deprecation(self, project):
        deprecations.reset_deprecations()
        with pytest.raises(EventCompilationError):
            run_dbt(["--warn-error-options", "{'error': 'all'}", "parse"])

        with pytest.raises(EventCompilationError):
            run_dbt(
                ["--warn-error-options", "{'error': ['ProjectFlagsMovedDeprecation']}", "parse"]
            )

        _, logs = run_dbt_and_capture(
            ["--warn-error-options", "{'silence': ['ProjectFlagsMovedDeprecation']}", "parse"]
        )
        assert (
            "User config should be moved from the 'config' key in profiles.yml to the 'flags' key in dbt_project.yml."
            not in logs
        )


class TestShowAllDeprecationsFlag:
    @pytest.fixture(scope="class")
    def models(self):
        return {"already_exists.sql": models_trivial__model_sql}

    @pytest.fixture(scope="class")
    def packages(self):
        return {
            "packages": [
                {"package": "fishtown-analytics/dbt_utils", "version": "0.7.0"},
                {"package": "calogica/dbt_date", "version": "0.10.0"},
            ]
        }

    @pytest.fixture(scope="class")
    def event_catcher(self) -> EventCatcher:
        return EventCatcher(event_to_catch=PackageRedirectDeprecation)

    def test_package_redirect(self, project, event_catcher: EventCatcher):
        deprecations.reset_deprecations()
        assert deprecations.active_deprecations == defaultdict(int)
        run_dbt(["deps"], callbacks=[event_catcher.catch])
        assert "package-redirect" in deprecations.active_deprecations
        assert deprecations.active_deprecations["package-redirect"] == 2
        assert len(event_catcher.caught_events) == 1

        deprecations.reset_deprecations()
        _get_cached.cache = {}
        event_catcher.flush()
        run_dbt(["deps", "--show-all-deprecations"], callbacks=[event_catcher.catch])
        assert "package-redirect" in deprecations.active_deprecations
        assert deprecations.active_deprecations["package-redirect"] == 2
        assert len(event_catcher.caught_events) == 2


class TestDeprecationSummary:
    @pytest.fixture(scope="class")
    def models(self):
        return {"already_exists.sql": models_trivial__model_sql}

    @pytest.fixture(scope="class")
    def packages(self):
        return {
            "packages": [
                {"package": "fishtown-analytics/dbt_utils", "version": "0.7.0"},
                {"package": "calogica/dbt_date", "version": "0.10.0"},
            ]
        }

    @pytest.fixture(scope="class")
    def event_catcher(self) -> EventCatcher:
        return EventCatcher(event_to_catch=DeprecationsSummary)

    def test_package_redirect(self, project, event_catcher: EventCatcher):
        deprecations.reset_deprecations()
        assert deprecations.active_deprecations == defaultdict(int)
        run_dbt(["deps"], callbacks=[event_catcher.catch])
        assert "package-redirect" in deprecations.active_deprecations
        assert deprecations.active_deprecations["package-redirect"] == 2
        assert len(event_catcher.caught_events) == 1
        for summary in event_catcher.caught_events[0].data.summaries:  # type: ignore
            found_summary = False
            if summary.event_name == "PackageRedirectDeprecation":
                assert (
                    summary.occurrences == 2
                ), f"Expected 2 occurrences of PackageRedirectDeprecation, got {summary.occurrences}"
                found_summary = True

        assert found_summary, "Expected to find PackageRedirectDeprecation in deprecations summary"


@mock.patch("dbt.jsonschemas._JSONSCHEMA_SUPPORTED_ADAPTERS", {"postgres"})
class TestDeprecatedInvalidDeprecationDate:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "models_trivial.sql": models_trivial__model_sql,
            "models.yml": invalid_deprecation_date_yaml,
        }

    @mock.patch.dict(os.environ, {"DBT_ENV_PRIVATE_RUN_JSONSCHEMA_VALIDATIONS": "True"})
    def test_deprecated_invalid_deprecation_date(self, project):
        event_catcher = EventCatcher(GenericJSONSchemaValidationDeprecation)
        note_catcher = EventCatcher(Note)
        try:
            run_dbt(
                ["parse", "--no-partial-parse"],
                callbacks=[event_catcher.catch, note_catcher.catch],
            )
        except:  # noqa
            assert (
                True
            ), "Expected an exception to be raised, because a model object can't be created with a deprecation_date as an int"

        # type-based jsonschema validation is not enabled, so no deprecations are raised even though deprecation_date is an int
        assert len(event_catcher.caught_events) == 0
        assert len(note_catcher.caught_events) == 0


class TestDuplicateYAMLKeysInSchemaFiles:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "models_trivial.sql": models_trivial__model_sql,
            "models.yml": duplicate_keys_yaml,
        }

    def test_duplicate_yaml_keys_in_schema_files(self, project):
        event_catcher = EventCatcher(DuplicateYAMLKeysDeprecation)
        run_dbt(["parse", "--no-partial-parse"], callbacks=[event_catcher.catch])
        assert len(event_catcher.caught_events) == 1
        assert (
            "Duplicate key 'models' in \"<unicode string>\", line 6, column 1 in file"
            in event_catcher.caught_events[0].info.msg
        )


class TestCustomKeyInConfigDeprecation:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "models_trivial.sql": models_trivial__model_sql,
            "models.yml": custom_key_in_config_yaml,
        }

    @mock.patch("dbt.jsonschemas._JSONSCHEMA_SUPPORTED_ADAPTERS", {"postgres"})
    @mock.patch.dict(os.environ, {"DBT_ENV_PRIVATE_RUN_JSONSCHEMA_VALIDATIONS": "True"})
    def test_custom_key_in_config_deprecation(self, project):
        event_catcher = EventCatcher(CustomKeyInConfigDeprecation)
        run_dbt(
            ["parse", "--no-partial-parse", "--show-all-deprecations"],
            callbacks=[event_catcher.catch],
        )
        assert len(event_catcher.caught_events) == 1
        assert (
            "Custom key `my_custom_key` found in `config` at path `models[0].config`"
            in event_catcher.caught_events[0].info.msg
        )


class TestMultipleCustomKeysInConfigDeprecation:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "models_trivial.sql": models_trivial__model_sql,
            "models.yml": multiple_custom_keys_in_config_yaml,
        }

    @mock.patch("dbt.jsonschemas._JSONSCHEMA_SUPPORTED_ADAPTERS", {"postgres"})
    @mock.patch.dict(os.environ, {"DBT_ENV_PRIVATE_RUN_JSONSCHEMA_VALIDATIONS": "True"})
    def test_multiple_custom_keys_in_config_deprecation(self, project):
        event_catcher = EventCatcher(CustomKeyInConfigDeprecation)
        run_dbt(
            ["parse", "--no-partial-parse", "--show-all-deprecations"],
            callbacks=[event_catcher.catch],
        )
        assert len(event_catcher.caught_events) == 2
        assert (
            "Custom key `my_custom_key` found in `config` at path `models[0].config`"
            in event_catcher.caught_events[0].info.msg
        )
        assert (
            "Custom key `my_custom_key2` found in `config` at path `models[0].config`"
            in event_catcher.caught_events[1].info.msg
        )


class TestCustomKeyInObjectDeprecation:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "models_trivial.sql": models_trivial__model_sql,
            "models.yml": custom_key_in_object_yaml,
        }

    @mock.patch("dbt.jsonschemas._JSONSCHEMA_SUPPORTED_ADAPTERS", {"postgres"})
    @mock.patch.dict(os.environ, {"DBT_ENV_PRIVATE_RUN_JSONSCHEMA_VALIDATIONS": "True"})
    def test_custom_key_in_object_deprecation(self, project):
        event_catcher = EventCatcher(CustomKeyInObjectDeprecation)
        run_dbt(["parse", "--no-partial-parse"], callbacks=[event_catcher.catch])
        assert len(event_catcher.caught_events) == 1
        assert (
            "Custom key `my_custom_property` found at `models[0]` in file"
            in event_catcher.caught_events[0].info.msg
        )


class TestJsonschemaValidationDeprecationsArentRunWithoutEnvVar:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "models_trivial.sql": models_trivial__model_sql,
            "models.yml": custom_key_in_object_yaml,
        }

    def test_jsonschema_validation_deprecations_arent_run_without_env_var(self, project):
        event_catcher = EventCatcher(CustomKeyInObjectDeprecation)
        run_dbt(["parse", "--no-partial-parse"], callbacks=[event_catcher.catch])
        assert len(event_catcher.caught_events) == 0


class TestCustomOutputPathInSourceFreshnessDeprecation:
    @pytest.fixture(scope="class")
    def models(self):
        return {}

    def test_jsonschema_validation_deprecations_arent_run_without_env_var(
        self, project, project_root
    ):
        event_catcher = EventCatcher(CustomOutputPathInSourceFreshnessDeprecation)

        write_file(yaml.safe_dump({}), project_root, "custom_output.json")
        run_dbt(
            ["source", "freshness", "--output", "custom_output.json"],
            callbacks=[event_catcher.catch],
        )
        assert len(event_catcher.caught_events) == 1


class TestHappyPathProjectHasNoDeprecations:
    @mock.patch.dict(os.environ, {"DBT_ENV_PRIVATE_RUN_JSONSCHEMA_VALIDATIONS": "True"})
    def test_happy_path_project_has_no_deprecations(self, happy_path_project):
        event_cathcer = EventCatcher(DeprecationsSummary)
        run_dbt(
            ["parse", "--no-partial-parse", "--show-all-deprecations"],
            callbacks=[event_cathcer.catch],
        )
        assert len(event_cathcer.caught_events) == 0


class TestBaseProjectHasNoDeprecations:
    @mock.patch.dict(os.environ, {"DBT_ENV_PRIVATE_RUN_JSONSCHEMA_VALIDATIONS": "True"})
    def test_base_project_has_no_deprecations(self, project):
        event_cathcer = EventCatcher(DeprecationsSummary)
        run_dbt(
            ["parse", "--no-partial-parse", "--show-all-deprecations"],
            callbacks=[event_cathcer.catch],
        )
        assert len(event_cathcer.caught_events) == 0


class TestWEOIncludeExcludeDeprecation:
    @pytest.mark.parametrize(
        "include_error,exclude_warn,expect_deprecation",
        [
            ("include", "exclude", 1),
            ("include", "warn", 1),
            ("error", "exclude", 1),
            ("error", "warn", 0),
        ],
    )
    def test_weo_include_exclude_deprecation(
        self,
        project,
        include_error: str,
        exclude_warn: str,
        expect_deprecation: int,
    ):
        event_catcher = EventCatcher(WEOIncludeExcludeDeprecation)
        warn_error_options = f"{{'{include_error}': 'all', '{exclude_warn}': ['Deprecations']}}"
        run_dbt(
            ["parse", "--show-all-deprecations", "--warn-error-options", warn_error_options],
            callbacks=[event_catcher.catch],
        )

        assert len(event_catcher.caught_events) == expect_deprecation
        if expect_deprecation > 0:
            if include_error == "include":
                assert "include" in event_catcher.caught_events[0].info.msg
            else:
                assert "include" not in event_catcher.caught_events[0].info.msg
            if exclude_warn == "exclude":
                assert "exclude" in event_catcher.caught_events[0].info.msg
            else:
                assert "exclude" not in event_catcher.caught_events[0].info.msg


class TestModulesItertoolsDeprecation:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "models_itertools.sql": """
            {%- set A = [1] -%}
            {%- set B = ['x'] -%}
            {%- set AB_cartesian = modules.itertools.product(A, B) -%}

            {%- for item in AB_cartesian %}
              select {{ item[0] }}
            {%- endfor -%}
            """,
        }

    def test_models_itertools(self, project):
        event_catcher = EventCatcher(ModulesItertoolsUsageDeprecation)

        run_dbt(["run", "--no-partial-parse"], callbacks=[event_catcher.catch])

        assert len(event_catcher.caught_events) == 1
        assert (
            "Usage of itertools modules is deprecated" in event_catcher.caught_events[0].info.msg
        )

        assert (
            read_file("target/compiled/test/models/models_itertools.sql").strip()
            == "select 1".strip()
        )


class TestNoModulesItertoolsDeprecation:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "models_itertools.sql": "select {{ modules.datetime.datetime.now() }}",
        }

    def test_models_itertools(self, project):
        event_catcher = EventCatcher(ModulesItertoolsUsageDeprecation)

        run_dbt(["parse", "--no-partial-parse"], callbacks=[event_catcher.catch])

        assert len(event_catcher.caught_events) == 0


class TestModelsParamUsageDeprecation:

    @mock.patch.object(sys, "argv", ["dbt", "ls", "--models", "some_model"])
    def test_models_usage(self, project):
        event_catcher = EventCatcher(ModelParamUsageDeprecation)

        assert len(event_catcher.caught_events) == 0
        run_dbt(
            ["ls", "--models", "some_model"],
            callbacks=[event_catcher.catch],
        )
        assert len(event_catcher.caught_events) == 1


class TestModelsParamUsageRunnerDeprecation:

    def test_models_usage(self, project):
        event_catcher = EventCatcher(ModelParamUsageDeprecation)

        assert len(event_catcher.caught_events) == 0
        dbtRunner(callbacks=[event_catcher.catch]).invoke(["ls", "--models", "some_model"])
        assert len(event_catcher.caught_events) == 1


class TestModelParamUsageDeprecation:
    @mock.patch.object(sys, "argv", ["dbt", "ls", "--model", "some_model"])
    def test_model_usage(self, project):
        event_catcher = EventCatcher(ModelParamUsageDeprecation)

        assert len(event_catcher.caught_events) == 0
        run_dbt(
            ["ls", "--model", "some_model"],
            callbacks=[event_catcher.catch],
        )
        assert len(event_catcher.caught_events) == 1


class TestModelParamUsageRunnerDeprecation:

    def test_model_usage(self, project):
        event_catcher = EventCatcher(ModelParamUsageDeprecation)

        assert len(event_catcher.caught_events) == 0
        dbtRunner(callbacks=[event_catcher.catch]).invoke(["ls", "--model", "some_model"])
        assert len(event_catcher.caught_events) == 1


class TestMParamUsageDeprecation:
    @mock.patch.object(sys, "argv", ["dbt", "ls", "-m", "some_model"])
    def test_m_usage(self, project):
        event_catcher = EventCatcher(ModelParamUsageDeprecation)

        assert len(event_catcher.caught_events) == 0
        run_dbt(
            ["ls", "-m", "some_model"],
            callbacks=[event_catcher.catch],
        )
        assert len(event_catcher.caught_events) == 1


class TestMParamUsageRunnerDeprecation:
    def test_m_usage(self, project):
        event_catcher = EventCatcher(ModelParamUsageDeprecation)

        assert len(event_catcher.caught_events) == 0
        dbtRunner(callbacks=[event_catcher.catch]).invoke(["ls", "-m", "some_model"])
        assert len(event_catcher.caught_events) == 1


class TestSelectParamNoModelUsageDeprecation:

    @mock.patch.object(sys, "argv", ["dbt", "ls", "--select", "some_model"])
    def test_select_usage(self, project):
        event_catcher = EventCatcher(ModelParamUsageDeprecation)

        assert len(event_catcher.caught_events) == 0
        run_dbt(
            ["ls", "--select", "some_model"],
            callbacks=[event_catcher.catch],
        )
        assert len(event_catcher.caught_events) == 0


class TestSelectParamNoModelUsageRunnerDeprecation:
    def test_select_usage(self, project):
        event_catcher = EventCatcher(ModelParamUsageDeprecation)

        assert len(event_catcher.caught_events) == 0
        dbtRunner(callbacks=[event_catcher.catch]).invoke(["ls", "--select", "some_model"])
        assert len(event_catcher.caught_events) == 0


class TestEnvironmentVariableNamespaceDeprecation:
    @mock.patch.dict(
        os.environ,
        {
            "DBT_ENGINE_PARTIAL_PARSE": "False",
            "DBT_ENGINE_MY_CUSTOM_ENV_VAR_FOR_TESTING": "True",
        },
    )
    def test_environment_variable_namespace_deprecation(self):
        event_catcher = EventCatcher(event_to_catch=EnvironmentVariableNamespaceDeprecation)

        run_dbt(["parse", "--show-all-deprecations"], callbacks=[event_catcher.catch])
        assert len(event_catcher.caught_events) == 1
        assert (
            "DBT_ENGINE_MY_CUSTOM_ENV_VAR_FOR_TESTING"
            == event_catcher.caught_events[0].data.env_var
        )


class TestMissingPlusPrefixDeprecation:
    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"seeds": {"path": {"enabled": True}}}

    @mock.patch.dict(os.environ, {"DBT_ENV_PRIVATE_RUN_JSONSCHEMA_VALIDATIONS": "True"})
    @mock.patch("dbt.jsonschemas._JSONSCHEMA_SUPPORTED_ADAPTERS", {"postgres"})
    def test_missing_plus_prefix_deprecation(self, project):
        event_catcher = EventCatcher(MissingPlusPrefixDeprecation)
        run_dbt(["parse", "--no-partial-parse"], callbacks=[event_catcher.catch])
        assert len(event_catcher.caught_events) == 1
        assert "Missing '+' prefix on `enabled`" in event_catcher.caught_events[0].info.msg


class TestMissingPlusPrefixDeprecationSubPath:
    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"seeds": {"path": {"+enabled": True, "sub_path": {"enabled": True}}}}

    @mock.patch.dict(os.environ, {"DBT_ENV_PRIVATE_RUN_JSONSCHEMA_VALIDATIONS": "True"})
    @mock.patch("dbt.jsonschemas._JSONSCHEMA_SUPPORTED_ADAPTERS", {"postgres"})
    def test_missing_plus_prefix_deprecation_sub_path(self, project):
        event_catcher = EventCatcher(MissingPlusPrefixDeprecation)
        run_dbt(["parse", "--no-partial-parse"], callbacks=[event_catcher.catch])
        assert len(event_catcher.caught_events) == 1
        assert "Missing '+' prefix on `enabled`" in event_catcher.caught_events[0].info.msg


class TestMissingPlusPrefixDeprecationCustomConfig:
    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"seeds": {"path": {"custom_config": True, "sub_path": {"+enabled": True}}}}

    @mock.patch.dict(os.environ, {"DBT_ENV_PRIVATE_RUN_JSONSCHEMA_VALIDATIONS": "True"})
    @mock.patch("dbt.jsonschemas._JSONSCHEMA_SUPPORTED_ADAPTERS", {"postgres"})
    def test_missing_plus_prefix_deprecation_sub_path(self, project):
        event_catcher = EventCatcher(MissingPlusPrefixDeprecation)
        run_dbt(["parse", "--no-partial-parse"], callbacks=[event_catcher.catch])
        assert len(event_catcher.caught_events) == 1
        assert "Missing '+' prefix on `custom_config`" in event_catcher.caught_events[0].info.msg


class TestCustomConfigInDbtProjectYmlNoDeprecation:
    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {"seeds": {"path": {"+custom_config": True}}}

    @mock.patch.dict(os.environ, {"DBT_ENV_PRIVATE_RUN_JSONSCHEMA_VALIDATIONS": "True"})
    @mock.patch("dbt.jsonschemas._JSONSCHEMA_SUPPORTED_ADAPTERS", {"postgres"})
    def test_missing_plus_prefix_deprecation_sub_path(self, project):
        note_catcher = EventCatcher(Note)
        run_dbt(["parse", "--no-partial-parse"], callbacks=[note_catcher.catch])
        assert len(note_catcher.caught_events) == 0


class TestJsonSchemaValidationGating:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "models_trivial.sql": models_trivial__model_sql,
            "models.yml": custom_key_in_config_yaml,
        }

    @pytest.mark.parametrize(
        "postgres_is_valid,dbt_private_run_jsonschema_validations,expected_events",
        [
            (True, "True", 1),
            (False, "True", 0),
            (False, "False", 0),
            (False, "False", 0),
        ],
    )
    def test_jsonschema_validation_gating(
        self,
        project,
        mocker: MockerFixture,
        postgres_is_valid: bool,
        dbt_private_run_jsonschema_validations: bool,
        expected_events: int,
    ) -> None:
        mocker.patch.dict(
            os.environ,
            {"DBT_ENV_PRIVATE_RUN_JSONSCHEMA_VALIDATIONS": dbt_private_run_jsonschema_validations},
        )

        if postgres_is_valid:
            supported_adapters_with_postgres = {
                "postgres",
                "bigquery",
                "databricks",
                "redshift",
                "snowflake",
            }
            mocker.patch(
                "dbt.jsonschemas._JSONSCHEMA_SUPPORTED_ADAPTERS", supported_adapters_with_postgres
            )

        event_catcher = EventCatcher(CustomKeyInConfigDeprecation)
        run_dbt(
            ["parse", "--no-partial-parse", "--show-all-deprecations"],
            callbacks=[event_catcher.catch],
        )
        assert len(event_catcher.caught_events) == expected_events


class TestArgumentsPropertyInGenericTestDeprecation:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "models_trivial.sql": models_trivial__model_sql,
            "models.yml": test_with_arguments_yaml,
        }

    def test_arguments_property_in_generic_test_deprecation(self, project):
        event_catcher = EventCatcher(ArgumentsPropertyInGenericTestDeprecation)
        run_dbt(
            ["parse", "--no-partial-parse", "--show-all-deprecations"],
            callbacks=[event_catcher.catch],
        )
        assert len(event_catcher.caught_events) == 4


class TestArgumentsPropertyInGenericTestDeprecationBehaviorChange:
    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {
            "config-version": 2,
            "flags": {
                "require_generic_test_arguments_property": True,
            },
        }

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "models_trivial.sql": models_trivial__model_sql,
            "models.yml": test_with_arguments_yaml,
        }

    def test_arguments_property_in_generic_test_deprecation(self, project):
        event_catcher = EventCatcher(ArgumentsPropertyInGenericTestDeprecation)
        run_dbt(
            ["parse", "--no-partial-parse", "--show-all-deprecations"],
            callbacks=[event_catcher.catch],
        )
        assert len(event_catcher.caught_events) == 0


class TestMissingArgumentsPropertyInGenericTestDeprecation:
    @pytest.fixture(scope="class")
    def project_config_update(self):
        return {
            "config-version": 2,
            "flags": {
                "require_generic_test_arguments_property": True,
            },
        }

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "models_trivial.sql": models_trivial__model_sql,
            "models.yml": test_missing_arguments_property_yaml,
        }

    def test_missing_arguments_property_in_generic_test_deprecation(self, project):
        event_catcher = EventCatcher(MissingArgumentsPropertyInGenericTestDeprecation)
        run_dbt(
            ["parse", "--no-partial-parse", "--show-all-deprecations"],
            callbacks=[event_catcher.catch],
        )
        assert len(event_catcher.caught_events) == 4
