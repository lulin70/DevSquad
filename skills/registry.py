"""Sub-skill registry: discover and instantiate skills by name."""

import importlib
from pathlib import Path

_SKILL_DIR = Path(__file__).parent
_AVAILABLE_SKILLS: dict[str, type] = {}


class BaseSkill:
    """Base class for all DevSquad sub-skills."""

    name: str = ""
    description: str = ""
    version: str = "3.6.8"

    def run(self, *args, **kwargs):
        raise NotImplementedError

    def info(self) -> dict:
        return {"name": self.name, "description": self.description, "version": self.version}


def _load_skill(name: str) -> type[BaseSkill] | None:
    skill_dir = _SKILL_DIR / name
    if not skill_dir.is_dir():
        return None
    handler_path = skill_dir / "handler.py"
    if not handler_path.exists():
        return None
    try:
        mod = importlib.import_module(f"skills.{name}.handler")
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if isinstance(attr, type) and issubclass(attr, BaseSkill) and attr is not BaseSkill:
                return attr
    except Exception:
        pass
    return None


def get_skill(name: str) -> BaseSkill:
    """Get a skill instance by name. Lazy-loads on first access."""
    if name not in _AVAILABLE_SKILLS:
        cls = _load_skill(name)
        if cls is None:
            raise ValueError(f"Skill '{name}' not found. Available: {list_skills()}")
        _AVAILABLE_SKILLS[name] = cls
    return _AVAILABLE_SKILLS[name]()


def list_skills() -> list:
    """List all available sub-skill names."""
    if not _AVAILABLE_SKILLS:
        for d in sorted(_SKILL_DIR.iterdir()):
            if d.is_dir() and (d / "handler.py").exists():
                cls = _load_skill(d.name)
                if cls:
                    _AVAILABLE_SKILLS[d.name] = cls
    return list(_AVAILABLE_SKILLS.keys())


def discover_all() -> dict[str, BaseSkill]:
    """Instantiate all available skills."""
    names = list_skills()
    return {name: get_skill(name) for name in names}
