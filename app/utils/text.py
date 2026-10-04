import re

# Applied after compacting (lowercase, symbols mapped, non-alphanumerics removed).
TECH_ALIASES: dict[str, str] = {
    "node": "nodejs",
    "postgres": "postgresql",
    "psql": "postgresql",
    "js": "javascript",
    "ts": "typescript",
    "golang": "go",
    "vue": "vuejs",
    "react": "reactjs",
    "rn": "reactnative",
    "k8s": "kubernetes",
    "net": "dotnet",
    "mongo": "mongodb",
    "gcp": "googlecloud",
    "aws": "amazonwebservices",
}


def normalize_technology(name: str) -> str:
    """Canonical key for comparing technology names.

    "React Native", "react-native" and "ReactNative" all map to "reactnative";
    "Node.js" and "node" map to "nodejs"; "C++" -> "cplusplus", "C#" -> "csharp".
    """
    key = name.strip().lower().replace("+", "plus").replace("#", "sharp")
    key = re.sub(r"[^a-z0-9]", "", key)
    return TECH_ALIASES.get(key, key)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "criterion"
