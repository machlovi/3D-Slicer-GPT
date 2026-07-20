"""SKILL.md discovery and progressive disclosure.

A skill is a folder containing SKILL.md with YAML-ish frontmatter:

    ---
    name: ct-chest-demo
    description: Guided CT chest review workflow for demos
    ---
    <markdown instructions for the model>

Only the name + description of every skill is put in the system prompt; the
model loads the full body on demand via the `read_skill` tool. Skills live in
two places (user dir wins on name collision):

    <module>/skills/           built-in, ship with the module
    ~/.radassistant/skills/    user-authored
"""

import os
import re

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Skills that ship on disk but are hidden from the model (kept so nothing is lost,
# excluded from the system prompt). Adopts Talk2View's enabled/disabled-skills
# convention (its SkillsConfig has this; ours previously advertised every folder).
# These are non-English tutorial duplicates copied in from Talk2View — pure prompt
# noise for an English radiology assistant. Users can override via the file
# ~/.radassistant/skills_disabled.txt (one skill/folder name per line).
_DEFAULT_DISABLED = frozenset({
    "slicer-data-loading-visualization-french",
    "slicer-dicom-tutorial-french",
    "slicer-dicom-tutorial-portuguese",
    "slicer-dicom-tutorial-spanish",
    "slicer-welcome-tutorial-portuguese",
})


def _parse_frontmatter(text):
    """Return (fields_dict, body). Single tiny parser used everywhere."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    fields = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition(":")
            fields[key.strip().lower()] = value.strip().strip("\"'")
    return fields, text[match.end():]


class SkillLibrary:
    def __init__(self, builtin_dir, disabled=None):
        self._dirs = [
            builtin_dir,
            os.path.expanduser("~/.radassistant/skills"),
        ]
        self._disabled = set(_DEFAULT_DISABLED)
        if disabled:
            self._disabled |= set(disabled)
        self._disabled |= self._load_user_disabled()

    @staticmethod
    def _load_user_disabled():
        """Optional user override: ~/.radassistant/skills_disabled.txt, one name per
        line (# comments allowed). Defensive — never breaks skill discovery."""
        names = set()
        cfg = os.path.expanduser("~/.radassistant/skills_disabled.txt")
        try:
            with open(cfg, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        names.add(line)
        except OSError:
            pass
        return names

    def _scan(self):
        skills = {}
        for root in self._dirs:  # later dirs (user) override earlier ones
            if not os.path.isdir(root):
                continue
            for entry in sorted(os.listdir(root)):
                if entry in self._disabled:            # hidden by folder name
                    continue
                path = os.path.join(root, entry, "SKILL.md")
                if not os.path.isfile(path):
                    continue
                try:
                    with open(path, encoding="utf-8") as f:
                        fields, body = _parse_frontmatter(f.read())
                except OSError:
                    continue
                name = fields.get("name", entry)
                if name in self._disabled:             # hidden by skill name
                    continue
                skills[name] = {
                    "name": name,
                    "description": fields.get("description", ""),
                    "body": body.strip(),
                    "path": path,
                }
        return skills

    def list_for_prompt(self):
        """One line per skill for the system prompt."""
        skills = self._scan()
        if not skills:
            return "(no skills installed)"
        return "\n".join(
            f"- {s['name']}: {s['description']}" for s in skills.values()
        )

    def read(self, name):
        skills = self._scan()
        if name in skills:
            return skills[name]["body"]
        # forgiving match so the model can say "the chest demo skill"
        lowered = name.lower().strip()
        for skill in skills.values():
            if lowered in skill["name"].lower():
                return skill["body"]
        available = ", ".join(skills) or "(none)"
        return f"Error: no skill named '{name}'. Available skills: {available}"
