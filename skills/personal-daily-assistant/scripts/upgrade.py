#!/usr/bin/env python3
"""Stage a v0.2 workspace beside a portable v0.1 installation; never switch live jobs."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import shutil

spec = importlib.util.spec_from_file_location('portable_installer', Path(__file__).with_name('install.py'))
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

def upgrade(source_project, new_project, openclaw_config, *, apply=False, evening_ten_enabled=False):
    source = Path(source_project).expanduser().resolve()
    destination = Path(new_project).expanduser()
    if not destination.is_absolute(): raise ValueError('new project must be absolute')
    target = destination.resolve(strict=False)
    if installer._inside(target, source) or installer._inside(source, target): raise ValueError('Use a separate sibling workspace')
    fragment = json.loads((source / 'setup/openclaw-plugin-fragment.json').read_text())
    config = fragment['plugins']['entries']['personal-daily-transport']['config']
    guards = fragment['telegram_guardrails']
    data = Path(config['dataDir'])
    # Do not read the journal or pending contents, and do not create missing source data.
    if not all((data / name).is_file() and not (data / name).is_symlink() for name in ('events.jsonl', 'state.json')):
        raise ValueError('Existing regular journal and state files are required; inspect the old installation first')
    options = installer.InstallOptions(
        project_root=destination, data_dir=data, context_json=source / 'context/active_context.json',
        summaries_dir=Path(config['summariesDir']), timezone=config['timezone'],
        owner_telegram_id=config['ownerTelegramId'], telegram_target=guards['owner_id'],
        openclaw_config=Path(openclaw_config), openclaw_sessions_dir=Path(config['openclawSessionsDir']),
        token_file=Path(guards['token_file_reference']), thread_cleanup_cutoff=config['threadCleanupCutoff'],
        python_bin=config.get('pythonBin', 'python3'), evening_ten_enabled=evening_ten_enabled,
    )
    plan = installer.build_plan(options)
    if apply:
        installer.apply_install(options, plan)
        for name in ('active_context.json', 'active_context.md'):
            origin = source / 'context' / name
            if origin.is_file():
                shutil.copy2(origin, target / 'context' / name)
                (target / 'context' / name).chmod(0o600)
        previous_rules = source / 'AGENTS.md'
        if previous_rules.is_file(): shutil.copy2(previous_rules, target / 'setup/previous-AGENTS.md')
        plan['mode'] = 'staged-upgrade'
    plan['migration'] = {'source_project': str(source), 'shared_data_preserved': True, 'live_config_changed': False, 'live_schedules_changed': False,
                         'next_step': 'Stop old jobs, ingress and context writers BEFORE --apply and keep stopped until cutover. Back up data/config; review previous-AGENTS.md, switch plugin path and replace schedule keys, then verify. If the old context changed after staging, discard the staged copy and stage into another fresh path before cutover. Never run both installations simultaneously.'}
    return plan

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-project', type=Path, required=True)
    parser.add_argument('--new-project', type=Path, required=True)
    parser.add_argument('--openclaw-config', type=Path, required=True)
    parser.add_argument('--enable-evening-ten', action='store_true')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(upgrade(args.source_project, args.new_project, args.openclaw_config, apply=args.apply, evening_ten_enabled=args.enable_evening_ten), ensure_ascii=False, indent=2))
if __name__ == '__main__': main()
