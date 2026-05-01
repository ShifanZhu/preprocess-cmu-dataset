# Project Rules

## Repository-specific constraints
- Focus on `Systems/MCSystem`. Never read or edit other subsystems under `Systems/`. Read from `Systems/common` when necessary.

## Tests

## Static checks

## Benchmarks

## Environment and workflow

## Safety and approval

### Always allowed — read only
```
ls, find, tree, pwd, cd
cat, head, tail, less, wc
grep, rg, awk, sed (read-only)
git log, git status, git diff, git blame, git show
which, env, echo
file, stat
```

### Allowed — build and run
```
make -j4                 (from build folder only)
bin/run_mc e mc       (run/demo)
cmake --build, cmake -S   (inspect/build)
```

### Require confirmation — write
```
mkdir, cp, mv
touch
sed -i (in-place edit)
git add, git commit, git stash
```

### Require explicit user approval — destructive or external
```
rm, rmdir
git reset, git checkout, git rebase, git push
chmod, chown
curl, wget
pip install, apt install, npm install
kill, pkill
sudo (anything)
```

### Never allowed
```
git push --force
git reset --hard
rm -rf
```
