from pathlib import Path
from typing import Any
import logging

from dotenv import load_dotenv
from platformdirs import user_config_dir, user_data_dir

try:
    import tomllib as tomli
except ModuleNotFoundError:  # pragma: no cover
    import tomli

from config.config import Config
from utils.errors import ConfigError

logger = logging.getLogger(__name__)

APP_NAME = "code-it"
CONFIG_FILE_NAME = "config.toml"
AGENT_MD_FILE = "AGENT.MD"
PROJECT_CONFIG_DIR_NAME = ".ai-agent"


def get_config_dir() -> Path:
    return Path(user_config_dir(APP_NAME))


def get_data_dir() -> Path:
    return Path(user_data_dir(APP_NAME))


def ensure_config_dir() -> Path:
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_system_config_path() -> Path:
    return get_config_dir() / CONFIG_FILE_NAME


def _parse_toml(path: Path) -> dict[str, Any]:
    try:
        with open(path, "rb") as file_obj:
            data = tomli.load(file_obj)
            return data if isinstance(data, dict) else {}
    except tomli.TOMLDecodeError as error:
        raise ConfigError(
            f"Invalid TOML in {path}: {error}",
            config_file=str(path),
        ) from error
    except (OSError, IOError) as error:
        raise ConfigError(
            f"Failed to read config file {path}: {error}",
            config_file=str(path),
        ) from error


def _get_project_config(cwd: Path) -> Path | None:
    agent_dir = cwd.resolve() / PROJECT_CONFIG_DIR_NAME
    config_file = agent_dir / CONFIG_FILE_NAME
    if config_file.is_file():
        return config_file
    return None


def _get_agent_md_files(cwd: Path) -> str | None:
    agent_md_file = cwd.resolve() / AGENT_MD_FILE
    if agent_md_file.is_file():
        return agent_md_file.read_text(encoding="utf-8")
    return None


def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def _format_toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(_format_toml_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value: {type(value)!r}")


def _dumps_toml(data: dict[str, Any]) -> str:
    lines: list[str] = []

    scalars = {
        key: value
        for key, value in data.items()
        if not isinstance(value, dict) and value is not None
    }
    tables = {
        key: value
        for key, value in data.items()
        if isinstance(value, dict) and value
    }

    for key, value in scalars.items():
        lines.append(f"{key} = {_format_toml_value(value)}")

    for table_name, table_values in tables.items():
        if lines:
            lines.append("")
        lines.append(f"[{table_name}]")
        for key, value in table_values.items():
            if isinstance(value, dict):
                raise TypeError("Nested TOML tables beyond one level are not supported")
            if value is None:
                continue
            lines.append(f"{key} = {_format_toml_value(value)}")

    return "\n".join(lines) + "\n"


def save_system_config(updates: dict[str, Any]) -> Path:
    config_dir = ensure_config_dir()
    config_path = config_dir / CONFIG_FILE_NAME
    current: dict[str, Any] = {}

    if config_path.is_file():
        current = _parse_toml(config_path)

    merged = _merge_dicts(current, updates)
    config_path.write_text(_dumps_toml(merged), encoding="utf-8")
    return config_path


def load_config(cwd: Path | None) -> Config:
    cwd = cwd or Path.cwd()
    load_dotenv(cwd / ".env")

    system_path = get_system_config_path()
    config_dict: dict[str, Any] = {}

    if system_path.is_file():
        try:
            config_dict = _parse_toml(system_path)
        except ConfigError:
            logger.warning("Skipping invalid system config: %s", system_path)

    project_path = _get_project_config(cwd)
    if project_path:
        try:
            project_config_dict = _parse_toml(project_path)
            config_dict = _merge_dicts(config_dict, project_config_dict)
        except ConfigError:
            logger.warning("Skipping invalid project config: %s", project_path)

    if "cwd" not in config_dict:
        config_dict["cwd"] = cwd

    if "developer_instructions" not in config_dict:
        agent_md_content = _get_agent_md_files(cwd)
        if agent_md_content:
            config_dict["developer_instructions"] = agent_md_content

    try:
        return Config(**config_dict)
    except Exception as error:
        raise ConfigError(f"Invalid configuration: {error}") from error
