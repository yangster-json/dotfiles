---
name: safe-filesystem-search
description: Safe filesystem-discovery workflow for locating logs, artifacts, source, or files. Use before any recursive find, rg, grep -r, du, or similar filesystem search, especially when the requested path is broad, unknown, mounted, NFS-backed, or close to the filesystem root.
---

# Safe Filesystem Search

## Principle

Do not recursively search a broad filesystem tree just because the desired path is
not yet known. Bound discovery before traversing: use identifiers supplied by the
user, inspect one directory level at a time, and search only the smallest known
subtree.

## Prohibited broad traversals

Never run recursive `find`, `rg`, `grep -r`, `du`, or equivalent commands on:

- `/`, `/mnt`, `/tlogs`, `/home`, `~`, or another directory immediately below `/`
- an entire NFS, network, mounted, cache, build, or artifact volume
- a directory whose breadth and ownership are unknown

This includes apparently restrictive commands such as `find /mnt -name ...`.
A filename predicate does not prevent traversal of every directory beneath the
starting path.

Do not substitute a broad `rg --files`, `grep -r`, or shell glob for `find`; these
have the same traversal problem.

## Bounded discovery workflow

1. **Use known identifiers to construct a path.** Prefer an exact path from a
   server name, job name, build number, ticket title, artifact ID, hostname, or
   repository name.
2. **Inspect a single directory level.** Use `ls <known-directory>` or a bounded
   `find <known-directory> -maxdepth 1` before descending further.
3. **Filter before descending.** If a component is unknown, list the immediate
   parent and apply an exact-name filter (`rg '^exact-name$'` to the `ls` output).
4. **Search only the resulting leaf subtree.** Once an exact run, repository,
   workspace, or artifact directory is established, recursive file searches
   within it are allowed.
5. **Stop and ask.** If an exact small subtree cannot be identified in two or
   three bounded attempts, ask the user for the path or missing identifier.

Use explicit depth limits for structural inspection. Avoid commands that emit or
stat every file when directory names alone answer the question.

## Jenkins tlogs

For a Jenkins job/build, the tlog run directory is deterministic:

```text
/mnt/tlogs/<jenkins-server>/jobs/<job-name>/<build-number>
```

Example:

```bash
run=/mnt/tlogs/fwjenkins2/jobs/master_staging-wssd.pcie.gen4-wssd.direct_stress_drive_killer_pci_reset/155
ls -la "$run"
find "$run" -maxdepth 3 -type f -print
```

Never search `/mnt`, `/mnt/tlogs`, `/tlogs`, or an entire Jenkins `jobs` directory
recursively to find a Jenkins run. If the job name is unknown, list exactly:

```bash
ls -1 /mnt/tlogs/<jenkins-server>/jobs
```

and exact-filter that output. If the Jenkins server is unknown, obtain it from the
Jenkins URL or ask the user; do not search all tlog-server directories.

## Good and bad examples

Bad — walks every historical tlog job:

```bash
find /mnt/tlogs -type d -name '*pci_reset*'
rg -l 'power stats' /mnt
```

Good — examines only the specified run:

```bash
run=/mnt/tlogs/fwjenkins2/jobs/<job-name>/155
rg -n 'Power stats -  Summary' "$run/jenkins_logs/console_155.log"
```

Bad — recursively searches every repository and cache under home:

```bash
find ~ -name 'config.yaml'
```

Good — searches a known checkout:

```bash
find ~/work/project -type f -name 'config.yaml'
```

## Before executing a recursive command

Confirm all of the following:

- The starting directory is an intentional, task-relevant subtree.
- It is not a filesystem root, mount point, or broad shared collection.
- Its expected size is reasonably bounded.
- A direct path, `ls`, or shallow inspection cannot answer the question first.

If any answer is no, do not run the command.
