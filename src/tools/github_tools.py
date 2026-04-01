from __future__ import annotations

from src.tools.registry import ToolRegistry


def register_github_tools(registry: ToolRegistry, github_token: str) -> None:
    if not github_token:
        return

    from github import Github
    gh = Github(github_token)

    def list_repos(limit: int = 20) -> str:
        repos = list(gh.get_user().get_repos(sort="updated")[:limit])
        if not repos:
            return "Репозиториев не найдено."
        lines = [f"- {r.full_name} {'(private)' if r.private else '(public)'}" for r in repos]
        return "\n".join(lines)

    registry.register(
        name="list_repos",
        description="Показать список GitHub-репозиториев пользователя.",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Макс. количество (по умолчанию 20)"},
            },
        },
        handler=list_repos,
    )

    def list_issues(repo: str, state: str = "open", limit: int = 20) -> str:
        r = gh.get_repo(repo)
        issues = list(r.get_issues(state=state)[:limit])
        if not issues:
            return f"Issues ({state}) не найдено в {repo}."
        lines = []
        for i in issues:
            labels = ", ".join(l.name for l in i.labels) if i.labels else ""
            label_str = f" [{labels}]" if labels else ""
            lines.append(f"- #{i.number} {i.title}{label_str}")
        return "\n".join(lines)

    registry.register(
        name="list_issues",
        description="Показать issues в GitHub-репозитории.",
        input_schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Полное имя репозитория (owner/repo)"},
                "state": {"type": "string", "enum": ["open", "closed", "all"], "description": "Статус: open, closed, all"},
                "limit": {"type": "integer", "description": "Макс. количество"},
            },
            "required": ["repo"],
        },
        handler=list_issues,
    )

    def create_issue(repo: str, title: str, body: str = "") -> str:
        r = gh.get_repo(repo)
        issue = r.create_issue(title=title, body=body)
        return f"Issue #{issue.number} создан: {issue.html_url}"

    registry.register(
        name="create_issue",
        description="Создать новый issue в GitHub-репозитории.",
        input_schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Полное имя репозитория (owner/repo)"},
                "title": {"type": "string", "description": "Заголовок issue"},
                "body": {"type": "string", "description": "Описание issue (необязательно)"},
            },
            "required": ["repo", "title"],
        },
        handler=create_issue,
    )

    def list_prs(repo: str, state: str = "open", limit: int = 20) -> str:
        r = gh.get_repo(repo)
        prs = list(r.get_pulls(state=state)[:limit])
        if not prs:
            return f"Pull requests ({state}) не найдено в {repo}."
        lines = []
        for pr in prs:
            lines.append(f"- #{pr.number} {pr.title} ({pr.user.login})")
        return "\n".join(lines)

    registry.register(
        name="list_prs",
        description="Показать pull requests в GitHub-репозитории.",
        input_schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Полное имя репозитория (owner/repo)"},
                "state": {"type": "string", "enum": ["open", "closed", "all"]},
                "limit": {"type": "integer"},
            },
            "required": ["repo"],
        },
        handler=list_prs,
    )

    def get_pr(repo: str, number: int) -> str:
        r = gh.get_repo(repo)
        pr = r.get_pull(number)
        lines = [
            f"**#{pr.number} {pr.title}**",
            f"Автор: {pr.user.login}",
            f"Ветка: {pr.head.ref} → {pr.base.ref}",
            f"Статус: {pr.state}, mergeable={pr.mergeable}",
            f"Изменения: +{pr.additions} -{pr.deletions} ({pr.changed_files} файлов)",
        ]
        if pr.body:
            lines.append(f"\n{pr.body[:500]}")
        return "\n".join(lines)

    registry.register(
        name="get_pr",
        description="Показать детали pull request в GitHub.",
        input_schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "Полное имя репозитория"},
                "number": {"type": "integer", "description": "Номер PR"},
            },
            "required": ["repo", "number"],
        },
        handler=get_pr,
    )
