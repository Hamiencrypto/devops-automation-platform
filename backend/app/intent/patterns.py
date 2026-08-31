"""Regex pattern definitions for intent detection and entity extraction.

Each intent is a family of regex patterns. Higher-priority patterns appear
first. Patterns use named groups to capture entities (image, container,
port, path, etc.).

The Docker `deploy` family is now GENERIC: it matches any valid Docker
image reference (library image, user/image, registry/user/image:tag).
A small alias + fuzzy map catches common typos and spacing variants
like 'rabbbit mq' or 'mongo db'.
"""

import re
from dataclasses import dataclass, field
from typing import Pattern


@dataclass
class IntentPattern:
    """A single regex rule for one intent."""

    intent: str
    pattern: Pattern[str]
    entities: list[str] = field(default_factory=list)
    weight: float = 1.0
    example: str = ""


# =====================================================================
# Image alias / typo correction table
# =====================================================================
# Keys are lowercased, spaces-collapsed forms that users might type.
# Values are the canonical Docker Hub image names.
IMAGE_ALIASES: dict[str, str] = {
    # RabbitMQ typos and spacing
    "rabbitmq": "rabbitmq",
    "rabbitmg": "rabbitmq",
    "rabbbitmq": "rabbitmq",
    "rabitmq": "rabbitmq",
    "rabmq": "rabbitmq",
    "rabmq": "rabbitmq",
    "rabbitmqserver": "rabbitmq",
    "rabit": "rabbitmq",
    # MongoDB variants
    "mongodb": "mongo",
    "mongod": "mongo",
    "mogo": "mongo",
    "mongoodb": "mongo",
    # Postgres variants
    "postgres": "postgres",
    "postgresql": "postgres",
    "postgress": "postgres",
    "postgre": "postgres",
    "pgsql": "postgres",
    "psql": "postgres",
    # MySQL / MariaDB variants
    "mysql": "mysql",
    "mysqlserver": "mysql",
    "myslq": "mysql",
    "mariadb": "mariadb",
    "maria": "mariadb",
    # Redis
    "redis": "redis",
    "reddis": "redis",
    "redus": "redis",
    "redic": "redis",
    # Elasticsearch
    "elasticsearch": "elasticsearch",
    "elastic": "elasticsearch",
    "esearch": "elasticsearch",
    "elasticseach": "elasticsearch",
    "elasticserach": "elasticsearch",
    # Kafka
    "kafka": "bitnami/kafka",
    "apachekafka": "bitnami/kafka",
    # Nginx
    "nginx": "nginx",
    "nignx": "nginx",
    "ngnix": "nginx",
    "nginix": "nginx",
    # Others common
    "httpd": "httpd",
    "apache": "httpd",
    "apache2": "httpd",
    "memcached": "memcached",
    "memcache": "memcached",
    "grafana": "grafana/grafana",
    "prometheus": "prom/prometheus",
    "jenkins": "jenkins/jenkins",
    "gitea": "gitea/gitea",
    "gitlab": "gitlab/gitlab-ce",
    "portainer": "portainer/portainer-ce",
    "traefik": "traefik",
    "caddy": "caddy",
    "vault": "hashicorp/vault",
    "consul": "hashicorp/consul",
    "influxdb": "influxdb",
    "infludb": "influxdb",
    "minio": "minio/minio",
    "mino": "minio/minio",
    "busybox": "busybox",
    "alpine": "alpine",
    "ubuntu": "ubuntu",
    "debian": "debian",
    "fedora": "fedora",
    "python": "python",
    "node": "node",
    "nodejs": "node",
    "golang": "golang",
    "go": "golang",
}


def normalize_image_alias(raw: str) -> str:
    """Normalize a user-typed image token into a canonical image name.

    - Lowercases the input.
    - Strips surrounding whitespace and punctuation.
    - Collapses 2+ repeated letters to a single letter for fuzzy matching
      (so 'rabbbitmq' -> 'rabitmq' -> looked up).
    - Drops internal spaces (so 'rabbit mq' -> 'rabbitmq').
    - Looks up against the alias table; returns the original stripped
      value if no alias is found (caller can still attempt a pull).
    """
    if not raw:
        return raw
    token = raw.strip().lower().strip("'\"`,.;:()[]{}")
    # Keep a copy of the original (post-strip) for fallback
    compact = re.sub(r"\s+", "", token)
    # Direct hit on compact form
    if compact in IMAGE_ALIASES:
        return IMAGE_ALIASES[compact]
    # Collapse runs of the same char (rabbbit -> rabit) then retry
    collapsed = re.sub(r"(.)\1{1,}", r"\1", compact)
    if collapsed in IMAGE_ALIASES:
        return IMAGE_ALIASES[collapsed]
    # Try alphanum-only
    alphanum = re.sub(r"[^a-z0-9]", "", compact)
    if alphanum in IMAGE_ALIASES:
        return IMAGE_ALIASES[alphanum]
    # No alias hit — return the compact form (valid image refs have no spaces)
    return compact or token


# =====================================================================
# DOCKER patterns
# =====================================================================
# Valid Docker image reference: [registry/][user/]name[:tag]
# A permissive regex: first char alnum, then word chars, -, ., /, :
_IMG = r"(?P<image>[a-z0-9][a-z0-9._\-/: ]{0,128}?)"

DOCKER_PATTERNS = [
    # deploy/run/start/launch <image> [on port <N>]
    # The "on port N" clause is optional and stripped from the image by
    # the regex via a lookahead boundary.
    IntentPattern(
        intent="docker.deploy",
        pattern=re.compile(
            r"\b(?:deploy|run|start|spin\s*up|launch|bring\s*up|create\s+container)\b"
            r"\s+(?:the\s+|a\s+|an\s+)?"
            + _IMG +
            r"(?=\s*(?:$|on\s+port|port|:\d|,|\.|;|\band\b|\bwith\b))"
            r"(?:.*?(?:on\s+port|port|:)\s*(?P<port>\d{2,5}))?",
            re.IGNORECASE,
        ),
        entities=["image", "port"],
        weight=1.1,
        example="deploy nginx on port 8080",
    ),
    # Fallback: single-word deploy (e.g. "deploy rabbitmq", "run redis")
    # This handles the end-of-string case when no port / trailing clause is present.
    IntentPattern(
        intent="docker.deploy",
        pattern=re.compile(
            r"^\s*(?:please\s+)?(?:deploy|run|start|spin\s*up|launch)\s+"
            r"(?:the\s+|a\s+|an\s+)?"
            r"(?P<image>[a-z0-9][a-z0-9._\-/:]+(?:\s+[a-z0-9][a-z0-9._\-/:]+)?)"
            r"\s*$",
            re.IGNORECASE,
        ),
        entities=["image"],
        weight=1.0,
        example="deploy rabbitmq",
    ),
    # list containers
    IntentPattern(
        intent="docker.list",
        pattern=re.compile(
            r"\b(?:list|show|ls|get|display)\b.*\b(?:container|containers|docker\s+ps|running)\b",
            re.IGNORECASE,
        ),
        weight=1.0,
        example="list all containers",
    ),
    # stop <name>
    IntentPattern(
        intent="docker.stop",
        pattern=re.compile(
            r"\b(?:stop|kill|terminate|shut\s*down)\b"
            r"(?:\s+(?:the\s+)?container\s+)?\s+(?P<container>[\w\-.]+)",
            re.IGNORECASE,
        ),
        entities=["container"],
        weight=1.0,
        example="stop nginx-web",
    ),
    # remove <name>
    IntentPattern(
        intent="docker.remove",
        pattern=re.compile(
            r"\b(?:remove|rm|delete)\b\s+(?:container\s+)?(?P<container>[\w\-.]+)",
            re.IGNORECASE,
        ),
        entities=["container"],
        weight=0.9,
        example="remove container old-web",
    ),
    # status of <name>
    IntentPattern(
        intent="docker.status",
        pattern=re.compile(
            r"\b(?:status|info|inspect|stats)\b.*?(?:of\s+)?(?P<container>[\w\-.]+)",
            re.IGNORECASE,
        ),
        entities=["container"],
        weight=0.8,
        example="status of nginx-web",
    ),
    # logs of container
    IntentPattern(
        intent="docker.logs",
        pattern=re.compile(
            r"\b(?:container\s+logs|docker\s+logs)\s+(?P<container>[\w\-.]+)",
            re.IGNORECASE,
        ),
        entities=["container"],
        weight=1.1,
        example="container logs nginx-web",
    ),
]

# =====================================================================
# LOG analysis patterns
# =====================================================================
LOGS_PATTERNS = [
    IntentPattern(
        intent="logs.analyze",
        pattern=re.compile(
            r"\b(?:analyze|parse|inspect|examine)\b.*?\blog(?:s|file)?\b"
            r"(?:.*?(?:at|in|from|path)\s+(?P<path>[\w\-./]+))?",
            re.IGNORECASE,
        ),
        entities=["path"],
        weight=1.0,
        example="analyze logs at /var/log/nginx/access.log",
    ),
    IntentPattern(
        intent="logs.errors",
        pattern=re.compile(
            r"\b(?:find|show|list|count|get)\b.*?\berrors?\b"
            r"(?:.*?(?:in|from|at)\s+(?P<path>[\w\-./]+))?",
            re.IGNORECASE,
        ),
        entities=["path"],
        weight=1.0,
        example="find errors in app.log",
    ),
    IntentPattern(
        intent="logs.summary",
        pattern=re.compile(
            r"\b(?:summar(?:y|ize)|overview|stats?|statistics)\b.*?\blog",
            re.IGNORECASE,
        ),
        weight=0.9,
        example="summarize the logs",
    ),
    IntentPattern(
        intent="logs.tail",
        pattern=re.compile(
            r"\b(?:tail|last|recent)\b\s*(?P<lines>\d+)?\s*(?:lines?\s+of\s+)?"
            r"(?:.*?(?:in|from|at)\s+)?(?P<path>[\w\-./]+)?",
            re.IGNORECASE,
        ),
        entities=["lines", "path"],
        weight=0.7,
        example="tail 50 lines of app.log",
    ),
]

# =====================================================================
# FILE patterns
# =====================================================================
FILE_PATTERNS = [
    IntentPattern(
        intent="file.info",
        pattern=re.compile(
            r"\b(?:info|details|describe|what(?:\s+is|'s)?)\b.*?\bfile\b"
            r"(?:.*?(?P<path>[\w\-./]+\.\w+))?",
            re.IGNORECASE,
        ),
        entities=["path"],
        weight=0.9,
        example="info about file report.txt",
    ),
    IntentPattern(
        intent="file.count",
        pattern=re.compile(
            r"\b(?:count|how\s+many)\b\s+(?P<what>lines?|words?|characters?|chars?)"
            r"(?:.*?(?:in|of|from)\s+(?P<path>[\w\-./]+))?",
            re.IGNORECASE,
        ),
        entities=["what", "path"],
        weight=1.0,
        example="count lines in app.py",
    ),
    IntentPattern(
        intent="file.read",
        pattern=re.compile(
            r"\b(?:read|show|display|cat|view)\b\s+(?:file\s+)?(?P<path>[\w\-./]+\.\w+)",
            re.IGNORECASE,
        ),
        entities=["path"],
        weight=0.9,
        example="read file config.json",
    ),
    IntentPattern(
        intent="file.validate",
        pattern=re.compile(
            r"\b(?:validate|check|verify|lint)\b.*?(?P<path>[\w\-./]+\.\w+)",
            re.IGNORECASE,
        ),
        entities=["path"],
        weight=0.8,
        example="validate syntax of config.yaml",
    ),
]

# =====================================================================
# KUBERNETES patterns (bonus feature)
# =====================================================================
KUBERNETES_PATTERNS = [
    IntentPattern(
        intent="k8s.list_pods",
        pattern=re.compile(
            r"\b(?:list|show|get)\b.*?\bpods?\b"
            r"(?:.*?(?:in|namespace)\s+(?P<namespace>[\w\-]+))?",
            re.IGNORECASE,
        ),
        entities=["namespace"],
        weight=1.0,
        example="list pods in default namespace",
    ),
    IntentPattern(
        intent="k8s.deploy",
        pattern=re.compile(
            r"\b(?:deploy|apply|create)\b.*?\b(?:k8s|kubernetes|kube|deployment)\b"
            r"(?:.*?(?P<image>[\w\-.:/]+))?",
            re.IGNORECASE,
        ),
        entities=["image"],
        weight=1.2,  # outranks the generic docker.deploy pattern
        example="deploy kubernetes deployment with image myapp:v2",
    ),
    IntentPattern(
        intent="k8s.scale",
        pattern=re.compile(
            r"\bscale\b.*?(?P<resource>[\w\-]+)\s+(?:to\s+)?(?P<replicas>\d+)",
            re.IGNORECASE,
        ),
        entities=["resource", "replicas"],
        weight=1.0,
        example="scale deployment web to 5",
    ),
]

# =====================================================================
# SYSTEM patterns (bonus feature)
# =====================================================================
SYSTEM_PATTERNS = [
    IntentPattern(
        intent="system.health",
        pattern=re.compile(
            r"\b(?:system|server|host|platform)\s+(?:health|status|info|details)\b",
            re.IGNORECASE,
        ),
        weight=1.0,
        example="system health",
    ),
    IntentPattern(
        intent="system.disk",
        pattern=re.compile(
            r"\b(?:disk|storage|space)\s+(?:usage|free|available)\b",
            re.IGNORECASE,
        ),
        weight=1.0,
        example="disk usage",
    ),
    IntentPattern(
        intent="system.memory",
        pattern=re.compile(
            r"\b(?:memory|ram)\s+(?:usage|free|available)\b",
            re.IGNORECASE,
        ),
        weight=1.0,
        example="memory usage",
    ),
]


# =====================================================================
# ALL intent patterns, sorted by priority
# =====================================================================
ALL_PATTERNS: list[IntentPattern] = (
    KUBERNETES_PATTERNS  # Kubernetes first so "deploy k8s ..." wins over docker
    + DOCKER_PATTERNS
    + LOGS_PATTERNS
    + FILE_PATTERNS
    + SYSTEM_PATTERNS
)


# =====================================================================
# Destructive intents requiring explicit confirmation
# =====================================================================
DESTRUCTIVE_INTENTS: set[str] = {
    "docker.stop",
    "docker.remove",
    "k8s.scale",  # Arguably destructive if scaling down
}
