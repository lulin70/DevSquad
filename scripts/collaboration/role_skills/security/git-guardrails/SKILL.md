---
name: git-guardrails
description: Classify git commands into three-tier safety categories to prevent dangerous operations
---

# Git Guardrails

## Leading Words

Classify every git command into FORBIDDEN, NEEDS_REVIEW, or ALWAYS_SAFE before execution — force-push to protected branches, hard resets, and clean -f are blocked; push, merge, and rebase require review; status, log, and diff are always safe.

## Vocabulary (from GLOSSARY.md)

- **Protected branch**: `main` or `master`. Force-push and deletion to these branches is FORBIDDEN.
- **Three-tier classification**: FORBIDDEN (blocked) → NEEDS_REVIEW (requires approval) → ALWAYS_SAFE (auto-approved).
- **Force-push**: `git push --force` or `git push -f`. Rewrites remote history. FORBIDDEN on protected branches.
- **Destructive operation**: `reset --hard`, `clean -fd`, `branch -D` — these discard uncommitted or committed work permanently.

## Classification Rules

### FORBIDDEN (Blocked — never execute without explicit override)

| Command | Reason |
|---------|--------|
| `git push --force origin main` | Force-push to protected branch |
| `git push --force origin master` | Force-push to protected branch |
| `git push -f origin main` | Force-push (short form) to protected branch |
| `git reset --hard` | Discards all uncommitted changes permanently |
| `git clean -fd` | Deletes untracked files and directories permanently |
| `git branch -D <branch>` | Force-delete a branch (loses unmerged commits) |
| `git rebase -i` | Interactive rebase rewrites history (non-expert error-prone) |

### NEEDS_REVIEW (Requires approval — may modify shared state)

| Command | Reason |
|---------|--------|
| `git push` | Modifies remote (may conflict with others' work) |
| `git push origin <feature>` | Push to non-protected remote branch |
| `git merge <branch>` | Merges branch into current HEAD |
| `git rebase <branch>` | Rewrites local history onto another branch |
| `git cherry-pick <commit>` | Applies a commit from another branch |
| `git commit --amend` | Rewrites the last commit (changes hash) |
| `git stash drop` | Permanently deletes a stash entry |
| `git checkout <branch>` | Switches working tree (safe but changes context) |

### ALWAYS_SAFE (Auto-approved — read-only or local-only)

| Command | Reason |
|---------|--------|
| `git status` | Read working tree state |
| `git log` | Read commit history |
| `git diff` | Read changes |
| `git show` | Read a specific commit |
| `git add` | Stage files (local only, no remote effect) |
| `git fetch` | Download remote refs (does not modify working tree) |
| `git pull` | Fetch + merge (safe if no conflicts) |
| `git branch` | List branches (no flags) |
| `git stash` | Stash changes (local only, reversible via `stash pop`) |
| `git stash list` | List stashes (read-only) |
| `git stash pop` | Restore stashed changes (local, reversible) |

## Process Steps

### Step 1: Parse the Command

Use `shlex.split()` to robustly parse the git command string, handling quoted arguments and escape sequences.

### Step 2: Classify

```python
from scripts.collaboration.operation_classifier import OperationClassifier

classifier = OperationClassifier()
category = classifier.classify_git_command("git push --force origin main")
# Returns: "FORBIDDEN"

category = classifier.classify_git_command("git status")
# Returns: "ALWAYS_SAFE"
```

### Step 3: Enforce

- **FORBIDDEN**: Block execution. Log the attempt. Require explicit BYPASS permission + human approval.
- **NEEDS_REVIEW**: Pause execution. Request approval from user or AI reviewer. Log the decision.
- **ALWAYS_SAFE**: Execute immediately. No logging required.

### Step 4: Log

Record every NEEDS_REVIEW and FORBIDDEN command in the audit log with:
- Timestamp
- Command string
- Classification
- Approver (if approved)
- Execution result

## Failure Modes

- **"It's just a small push"**: Every push to a shared remote modifies shared state. Always classify as NEEDS_REVIEW.
- **"Force-push is fine, nobody else is working"**: Protected branches are protected for a reason. Even if you think nobody else is working, force-push is FORBIDDEN.
- **"reset --hard is quick"**: `reset --hard` discards all uncommitted work. Use `stash` first if unsure.
- **"I'll clean up later"**: `clean -fd` deletes untracked files permanently. There is no undo.

## Anti-Patterns

- Running `git push --force` without checking if the branch is protected
- Using `reset --hard` to discard changes instead of `stash`
- Running `clean -fd` without first checking `git status` for important untracked files
- Amending a commit that has already been pushed (creates divergent history)
- Interactive rebase on a shared branch

## Verification Requirements

- Every git command must be classified before execution
- FORBIDDEN commands must be logged with attempt timestamp
- NEEDS_REVIEW commands must have an recorded approval decision
- Protected branches (`main`, `master`) must never receive force-push
- Audit log must be retained for compliance (6+ months for production repos)
