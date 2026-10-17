"""Synthetic, local-only safety tests. No VM, real torrents, network or deletion."""
import copy
import importlib.util
import json
import os
import stat
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

MODULE = Path(__file__).resolve().parents[1]
SCRIPT = MODULE / 'scripts/torrent-cleanup.py'
spec = importlib.util.spec_from_file_location('torrent_cleanup', SCRIPT)
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
H = 'a' * 40
NOW = 2000000000


def torrent(complete=False, **changes):
    t = {'hash': H, 'name': 'Example release', 'category': 'movies', 'added_on': NOW - 200000,
         'completion_on': NOW - 7200 if complete else -1, 'amount_left': 0 if complete else 50,
         'progress': 1 if complete else .5, 'downloaded': 100 if complete else 50,
         'completed': 100 if complete else 50, 'time_active': 100000, 'dlspeed': 0,
         'state': 'stalledUP' if complete else 'stalledDL', 'force_start': False, 'tags': '',
         'save_path': '/data/downloads/movies', 'content_path': '/data/downloads/movies/Example/movie.mkv'}
    return {**t, **changes}


def files(complete=False):
    return [{'name': 'Example/movie.mkv', 'size': 100, 'priority': 1, 'progress': 1 if complete else .5}]


def rows(t=None, f=None):
    t = t or torrent()
    return C.manifest(t, f or files(t['progress'] == 1), {})


class MemoryAudit:
    def __init__(self):
        self.records = []

    def emit(self, event, t=None, **kwargs):
        self.records.append({'event': event, **kwargs})


class FakeAPI:
    def __init__(self, name, torrents=None):
        self.name = name
        self.data = {t['hash']: copy.deepcopy(t) for t in (torrents or [])}
        self.filemap = {t['hash']: files(t['progress'] == 1) for t in (torrents or [])}
        self.calls, self.history, self.queue, self.items = [], [], [], []
        self.fail = set()
        self.version = b'v5.2.4'
        self.health = {'connection_status': 'connected', 'dht_nodes': 100}

    def call(self, path, query=None, method='GET', form=None, raw=False):
        self.calls.append((path, query, method, form))
        if path in self.fail:
            raise C.Refused('api_request_failed')
        if path.endswith('/app/version'):
            return self.version
        if path.endswith('/transfer/info'):
            return self.health
        if path.endswith('/torrents/info'):
            return copy.deepcopy([v for k, v in self.data.items() if not query or query.get('hashes') == k])
        if path.endswith('/torrents/files'):
            return copy.deepcopy(self.filemap[query['hash']])
        if path.endswith('/torrents/properties'):
            return {}
        if path.endswith('/torrents/stop'):
            self.data[form['hashes']]['state'] = 'stoppedDL'
            self.data[form['hashes']]['dlspeed'] = 0
            return b''
        if path.endswith('/torrents/delete'):
            self.data.pop(form['hashes'])
            return b''
        if path.endswith('/history'):
            return {'records': copy.deepcopy(self.history), 'totalRecords': len(self.history)}
        if path.endswith('/queue'):
            return {'records': copy.deepcopy(self.queue), 'totalRecords': len(self.queue)}
        if method == 'DELETE' and '/queue/' in path:
            return b''
        if path == '/api/v3/system/status':
            return {'version': 'test'}
        if path == '/Items':
            return {'Items': copy.deepcopy(self.items), 'TotalRecordCount': len(self.items)}
        raise AssertionError((path, query, method))


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.audit = MemoryAudit()

    def runner(self, t=None, apply=False, policy='both', now=NOW):
        q = FakeAPI('qbittorrent', [t] if t else [])
        apis = {s: FakeAPI(s) for s in ('radarr', 'sonarr', 'jellyfin')}
        apis['qbittorrent'] = q
        r = C.Runner(apis, self.audit, self.home/'state.json', apply=apply, policy=policy,
                     clock=lambda: now, sleep=lambda _: None, boot_id='boot-one', connectivity=lambda: True)
        return r, q

    def mature(self, r, t, fs=None):
        r.state['observations'][H] = self.history(t, fs)

    def history(self, t, fs=None):
        fs = fs or rows(t)
        rec = None
        for ago in (86400, 64800, 43200, 21600):
            old = {**t, 'time_active': t['time_active'] - ago}
            rec, _ = C.observation(old, fs, rec, NOW - ago, True, 'boot-one')
        return rec

    def track(self, progresses, start=NOW, step=21600):
        rec = None
        for i, progress in enumerate(progresses):
            t = torrent(progress=progress, state='downloading', dlspeed=10, time_active=100000+i*step,
                        downloaded=int(progress*1000000), completed=int(progress*1000000),
                        amount_left=1000000-int(progress*1000000))
            fs = rows(t, [{**files()[0], 'size': 1000000, 'progress': progress}])
            rec, eligible = C.observation(t, fs, rec, start+i*step, True, 'boot-one')
        return rec, eligible

    def test_incomplete_minus_one_completion_time_is_valid(self):
        C.valid_torrent(torrent())

    def test_invalid_hash_and_nonfinite_numbers_refused(self):
        for change in ({'hash': 'all'}, {'progress': float('nan')}, {'downloaded': -1}, {'progress': 2}):
            with self.subTest(change=change), self.assertRaises(C.Refused):
                C.valid_torrent(torrent(**change))

    def test_exact_completion_minimum_and_unrounded_progress(self):
        t = torrent(True, completion_on=NOW-3600)
        self.assertTrue(C.complete_eligible(t, rows(t), NOW))
        for changes in ({'completion_on': NOW-3599}, {'completion_on': -1}, {'progress': .999999},
                        {'amount_left': 1}, {'state': 'checkingUP'}, {'state': 'moving'}, {'force_start': True},
                        {'added_on': NOW-1000}):
            with self.subTest(changes=changes):
                n = {**t, **changes}
                self.assertFalse(C.complete_eligible(n, rows(t), NOW))

    def test_complete_checks_every_wanted_file(self):
        t = torrent(True)
        f = files(True) + [{'name': 'Example/episode.mkv', 'size': 100, 'priority': 1, 'progress': .99}]
        self.assertFalse(C.complete_eligible(t, rows(t, f), NOW))

    def test_new_observation_does_not_use_added_on_or_last_activity(self):
        t = torrent(added_on=1, last_activity=1)
        rec, eligible = C.observation(t, rows(t), None, NOW, True, 'boot-one')
        self.assertFalse(eligible)
        self.assertEqual(rec['samples'], [{'time': NOW, 'progress': .5}])

    def test_24h_requires_four_six_hour_intervals(self):
        previous = None
        for step in range(5):
            t = torrent(time_active=step*21600)
            previous, eligible = C.observation(t, rows(t), previous, NOW+step*21600, True, 'boot-one')
            self.assertEqual(eligible, step == 4)

    def test_upload_activity_does_not_reset_stall_window(self):
        t = torrent()
        previous = self.history(t)
        t['last_activity'] = NOW
        _, eligible = C.observation(t, rows(t), previous, NOW, True, 'boot-one')
        self.assertTrue(eligible)

    def test_new_counters_do_not_reset_window_but_changed_selection_does(self):
        t = torrent()
        previous = self.history(t)
        for changed in (torrent(downloaded=51), torrent(completed=51)):
            with self.subTest(changed=changed):
                rec, eligible = C.observation(changed, rows(changed), previous, NOW, True, 'boot-one')
                self.assertTrue(eligible)
                self.assertEqual(rec['samples'][0]['time'], NOW-86400)
        f = files()+[{'name': 'other.mkv', 'size': 10, 'priority': 0, 'progress': 0}]
        rec, eligible = C.observation(t, rows(t, f), previous, NOW, True, 'boot-one')
        self.assertFalse(eligible)
        self.assertEqual(len(rec['samples']), 1)

    def test_pauses_queues_errors_and_forcing_not_counted_but_active_transfers_are(self):
        for state in ('stoppedDL', 'queuedDL', 'checkingDL', 'moving', 'missingFiles', 'error', 'metaDL', 'forcedDL'):
            t = torrent(state=state)
            self.assertFalse(C.observation(t, rows(t), None, NOW, True, 'boot-one')[0]['healthy'])
        t = torrent(force_start=True)
        self.assertFalse(C.observation(t, rows(t), None, NOW, True, 'boot-one')[0]['healthy'])
        t = torrent(state='downloading', dlspeed=1)
        self.assertTrue(C.observation(t, rows(t), None, NOW, True, 'boot-one')[0]['healthy'])

    def test_gap_restart_active_time_shortfall_and_clock_rollback_reset(self):
        t = torrent()
        previous = self.history(t)
        cases = [(NOW, False, 'boot-one', previous), (NOW, True, 'boot-two', previous),
                 (NOW+86400, True, 'boot-one', previous), (NOW-30000, True, 'boot-one', previous),
                 (NOW, True, 'boot-one', {**previous, 'active': t['time_active']-100})]
        for now, health, boot, old in cases:
            self.assertFalse(C.observation(t, rows(t), old, now, health, boot)[1])

    def test_marginal_progress_does_not_restart_daily_window(self):
        rec, eligible = self.track([.2, .2001, .2002, .2003, .2004])
        self.assertTrue(eligible)
        self.assertEqual(rec['samples'][0]['time'], NOW)
        self.assertEqual(C.progress_assessment(rec)['window_seconds'], 86400)

    def test_exact_five_points_pass_but_just_under_does_not(self):
        for end, expected in ((.25, False), (.250001, False), (.249999, True)):
            with self.subTest(end=end):
                rec, eligible = self.track([.2, .21, .22, .24, end])
                self.assertEqual(eligible, expected)
                self.assertEqual(C.progress_assessment(rec)['minimum_delta_percentage_points'], 5)

    def test_selected_size_weighted_progress_not_average_or_network_bytes(self):
        fs = rows(torrent(), [
            {'name': 'a.mkv', 'size': 1, 'priority': 1, 'progress': .99},
            {'name': 'b.mkv', 'size': 99, 'priority': 1, 'progress': 0},
            {'name': 'unselected.mkv', 'size': 1000000, 'priority': 0, 'progress': 1}])
        self.assertAlmostEqual(C.useful_progress(fs), .0099)
        with self.assertRaisesRegex(C.Refused, 'no_wanted_payload'):
            C.useful_progress([{**fs[0], 'priority': 0}])

    def test_window_rolls_and_old_burst_does_not_protect_forever(self):
        rec, eligible = self.track([.1, .2, .2, .2, .2])
        self.assertFalse(eligible)
        rec, eligible = self.track([.1, .2, .2, .2, .2, .2])
        self.assertTrue(eligible)
        self.assertEqual(rec['samples'][0]['time'], NOW+21600)

    def test_jitter_uses_real_older_anchor_without_interpolating(self):
        rec, eligible = self.track([.2, .21, .22, .23, .24], step=21660)
        self.assertTrue(eligible)
        self.assertEqual(C.progress_assessment(rec)['window_seconds'], 86640)
        # A burst between two samples cannot be placed inside/outside an exact day by guessing.
        rec, eligible = self.track([.1, .2, .2, .2, .2], step=21660)
        self.assertFalse(eligible)

    def test_frequent_manual_samples_are_bounded_and_cannot_shorten_window(self):
        rec, eligible = self.track([.5]*200, step=600)
        self.assertEqual(len(rec['samples']), C.MAX_SAMPLES)
        self.assertFalse(eligible)
        self.assertEqual(C.progress_assessment(rec)['reason'], 'insufficient_history')

    def test_ninety_percent_boundary_starts_grace_inclusively(self):
        for progress, expected in ((.89999, None), (.90, NOW), (.95, NOW)):
            with self.subTest(progress=progress):
                rec, eligible = self.track([progress])
                self.assertFalse(eligible)
                self.assertEqual(rec['near_complete_since'], expected)

    def test_near_complete_week_is_seven_days_not_seven_runs(self):
        rec, eligible = self.track([.95]*28)
        self.assertFalse(eligible)
        self.assertEqual(C.progress_assessment(rec)['reason'], 'near_complete_grace')
        rec, eligible = self.track([.95]*29)
        self.assertTrue(eligible)
        self.assertEqual(C.progress_assessment(rec)['near_complete_age_seconds'], 7*86400)

    def test_small_advances_do_not_restart_near_complete_week(self):
        rec, eligible = self.track([.90+i*.001 for i in range(29)])
        self.assertTrue(eligible)
        self.assertEqual(rec['near_complete_since'], NOW)

    def test_expired_grace_still_requires_insufficient_recent_progress(self):
        rec, eligible = self.track([.90]*25+[.9125, .925, .9375, .95])
        self.assertFalse(eligible)
        self.assertEqual(C.progress_assessment(rec)['reason'], 'sufficient_progress')
        self.assertEqual(rec['near_complete_since'], NOW)

    def test_full_completion_is_never_a_partial_candidate(self):
        rec, eligible = self.track([.95]*28+[1])
        self.assertFalse(eligible)
        self.assertFalse(rec['healthy'])
        self.assertTrue(C.complete_eligible(torrent(True), rows(torrent(True)), NOW))

    def test_pause_gap_or_boot_preserves_grace_but_requires_fresh_daily_samples(self):
        rec, _ = self.track([.95]*5)
        for state, boot, health in (('stoppedDL', 'boot-one', True), ('downloading', 'boot-two', True),
                                    ('downloading', 'boot-one', False)):
            t = torrent(progress=.95, downloaded=950000, completed=950000,
                        time_active=100000+3*86400, state=state)
            fs = rows(t, [{**files()[0], 'size': 1000000, 'progress': .95}])
            fresh, eligible = C.observation(t, fs, rec, NOW+3*86400, health, boot)
            self.assertFalse(eligible)
            self.assertEqual(fresh['near_complete_since'], NOW)
            self.assertEqual(len(fresh['samples']), 1)

    def test_regression_identity_change_and_clock_rollback_restart_grace(self):
        rec, _ = self.track([.96]*5)
        for changes, progress, now in (({'downloaded': 1}, .96, NOW+108000),
                                       ({'added_on': NOW}, .96, NOW+108000),
                                       ({}, .95, NOW+108000), ({}, .96, NOW)):
            t = torrent(progress=progress, downloaded=960000, completed=960000,
                        time_active=208000, **changes) if 'downloaded' not in changes else torrent(
                            progress=progress, completed=960000, time_active=208000, **changes)
            fs = rows(t, [{**files()[0], 'size': 1000000, 'progress': progress}])
            fresh, eligible = C.observation(t, fs, rec, now, True, 'boot-one')
            self.assertFalse(eligible)
            self.assertEqual(fresh['near_complete_since'], now)

    def test_invalid_sample_history_cannot_enable_deletion(self):
        rec = self.history(torrent())
        for bad in ({**rec, 'samples': [{'time': NOW+1, 'progress': .5}]},
                    {**rec, 'near_complete_since': NOW+1}, {**rec, 'progress': float('nan')},
                    {**rec, 'samples': list(reversed(rec['samples']))}):
            with self.subTest(bad=bad), self.assertRaises(C.Refused):
                C.observation(torrent(), rows(), bad, NOW, True, 'boot-one')

    def test_pruned_samples_match_full_history_oracle_with_timer_jitter(self):
        record, full, near = None, [], None
        now, progress = NOW, .85
        for i in range(60):
            now += 21600 + (i % 5 - 2)*30
            progress += .012 if i in (4, 10, 11, 38) else .0001
            t = torrent(progress=progress, state='downloading', downloaded=1000000*progress,
                        completed=1000000*progress, time_active=100000+now-NOW)
            fs = rows(t, [{**files()[0], 'size': 1000000, 'progress': progress}])
            record, eligible = C.observation(t, fs, record, now, True, 'boot-one')
            full.append({'time': now, 'progress': C.useful_progress(fs)})
            if C.at_least(progress, .90) and near is None:
                near = now
            anchors = [s for s in full if s['time'] <= now-86400]
            expected = (bool(anchors) and (near is None or now-near >= 7*86400)
                        and not C.at_least(full[-1]['progress']-anchors[-1]['progress'], .05))
            self.assertEqual(eligible, expected)
            C.validate_observation(record)
            self.assertLessEqual(len(record['samples']), 7)

    def test_paused_interval_cannot_count_toward_daily_window_after_resume(self):
        rec = self.history(torrent())
        t = torrent(state='stoppedDL')
        rec, eligible = C.observation(t, rows(t), rec, NOW, True, 'boot-one')
        self.assertFalse(eligible)
        for step in range(1, 6):
            t = torrent(time_active=100000+step*21600)
            rec, eligible = C.observation(t, rows(t), rec, NOW+step*21600, True, 'boot-one')
            self.assertEqual(eligible, step == 5)

    def test_partial_mixed_pack_including_unselected_complete_media_refused(self):
        f = files() + [{'name': 'Example/other.mkv', 'size': 100, 'priority': 0, 'progress': 1}]
        with self.assertRaisesRegex(C.Refused, 'mixed_complete_media'):
            C.partial_safe(rows(torrent(), f))

    def test_partial_without_media_refused(self):
        with self.assertRaises(C.Refused):
            C.partial_safe(rows(torrent(), [{'name': 'readme.txt', 'size': 100, 'priority': 1, 'progress': .5}]))

    def test_traversal_absolute_names_library_path_and_duplicates_refused(self):
        for name in ('../movie.mkv', '/media/movie.mkv', 'dir/../../movie.mkv', 'dir\\movie.mkv'):
            with self.subTest(name=name), self.assertRaises(C.Refused):
                rows(torrent(), [{**files()[0], 'name': name}])
        for t in (torrent(save_path='/data/media/movies'), torrent(content_path='/data/downloads')):
            with self.assertRaises(C.Refused):
                rows(t)
        with self.assertRaises(C.Refused):
            rows(torrent(), files()+files())

    def test_symlink_and_shared_hardlink_are_refused(self):
        root = self.home/'payload'
        root.mkdir()
        p = root/'partial.mkv'
        p.write_bytes(b'x')
        (root/'alias.mkv').hardlink_to(p)
        f = [{'media': True, 'priority': 1, 'size': 100, 'progress': .5, 'paths': [str(p)]}]
        with patch.object(C, 'checked_path', side_effect=lambda p, *a, **k: Path(p)):
            with self.assertRaisesRegex(C.Refused, 'shared_or_nonregular'):
                C.partial_safe(f)
        link = root/'escape'
        link.symlink_to(self.home/'other')
        with self.assertRaisesRegex(C.Refused, 'symlink'):
            C.checked_path(str(link/'file'), str(root))

    def test_empty_client_returns_without_manager_or_connectivity_queries(self):
        r, _ = self.runner()
        r.run()
        self.assertTrue(all(not r.apis[s].calls for s in ('radarr', 'sonarr', 'jellyfin')))

    def test_dry_run_never_sends_mutations_even_for_mature_stalled_candidate(self):
        t = torrent()
        r, q = self.runner(t)
        self.mature(r, t)
        r.apis['radarr'].queue = [{'id': 7, 'downloadId': H.upper()}]
        r.run()
        for api in r.apis.values():
            self.assertTrue(all(c[2] == 'GET' for c in api.calls))
        self.assertTrue(any(e['event'] == 'candidate' for e in self.audit.records))
        self.assertIn(H, q.data)

    def test_complete_dry_run_requires_import_and_jellyfin(self):
        r, q = self.runner(torrent(True))
        r.run()
        self.assertIn(H, q.data)
        self.assertFalse(any(e['event'] == 'candidate' for e in self.audit.records))
        self.assertIn('import_history_missing', [e.get('reason') for e in self.audit.records])

    def test_completed_apply_only_deletes_entry_false_and_rechecks_import(self):
        t = torrent(True)
        r, q = self.runner(t, apply=True)
        with patch.object(r, 'imported') as imported:
            r.run()
        self.assertEqual(imported.call_count, 2)
        mutations = [c for c in q.calls if c[2] != 'GET']
        self.assertEqual(len(mutations), 1)
        self.assertEqual(mutations[0][3], {'hashes': H, 'deleteFiles': 'false'})
        self.assertEqual(r.state['pending'], {})

    def test_stalled_apply_stops_blocks_without_search_then_deletes_payload(self):
        t = torrent()
        r, q = self.runner(t, apply=True)
        self.mature(r, t)
        r.apis['radarr'].queue = [{'id': 7, 'downloadId': H.upper()}]
        r.run()
        mutations = [c for c in q.calls if c[2] != 'GET']
        self.assertEqual([c[0].rsplit('/', 1)[-1] for c in mutations], ['stop', 'delete'])
        self.assertEqual(mutations[-1][3], {'hashes': H, 'deleteFiles': 'true'})
        arr = [c for c in r.apis['radarr'].calls if c[2] == 'DELETE']
        self.assertEqual(arr[0][1], {'removeFromClient': 'false', 'blocklist': 'true',
                                    'skipRedownload': 'true', 'changeCategory': 'false'})
        self.assertFalse(any('/command' in c[0] for a in r.apis.values() for c in a.calls))

    def test_active_slow_transfer_is_stopped_and_revalidated_before_deletion(self):
        t = torrent(state='downloading', dlspeed=100)
        r, q = self.runner(t, apply=True)
        self.mature(r, t)
        r.apis['radarr'].queue = [{'id': 7, 'downloadId': H}]
        r.run()
        self.assertNotIn(H, q.data)
        self.assertEqual(len([e for e in self.audit.records if e['event'] == 'revalidated']), 3)
        candidate = next(e for e in self.audit.records if e['event'] == 'candidate')
        self.assertEqual(candidate['window_seconds'], 86400)
        self.assertEqual(candidate['delta_percentage_points'], 0)

    def test_marginal_progress_during_stop_is_allowed_after_recheck(self):
        t = torrent(state='downloading', dlspeed=100)
        r, q = self.runner(t, apply=True)
        self.mature(r, t)
        r.apis['radarr'].queue = [{'id': 7, 'downloadId': H}]
        original = q.call
        def call(path, *a, **kw):
            result = original(path, *a, **kw)
            if path.endswith('/stop'):
                q.data[H].update(progress=.5001, downloaded=51, completed=51, amount_left=49)
                q.filemap[H][0]['progress'] = .5001
            return result
        q.call = call
        r.run()
        self.assertNotIn(H, q.data)
        self.assertFalse(r.state['pending'])

    def test_sufficient_progress_during_stop_blocks_partial_delete(self):
        t = torrent(state='downloading', dlspeed=100)
        r, q = self.runner(t, apply=True)
        self.mature(r, t)
        r.apis['radarr'].queue = [{'id': 7, 'downloadId': H}]
        original = q.call
        def call(path, *a, **kw):
            result = original(path, *a, **kw)
            if path.endswith('/stop'):
                q.data[H].update(progress=.55, downloaded=55, completed=55, amount_left=45)
                q.filemap[H][0]['progress'] = .55
            return result
        q.call = call
        with self.assertRaisesRegex(C.Refused, 'pending_action_requires_review'):
            r.run()
        self.assertIn(H, q.data)
        self.assertIn(H, r.state['pending'])
        self.assertFalse(any(c[0].endswith('/delete') for c in q.calls))
        self.assertFalse(any(c[2] == 'DELETE' for c in r.apis['radarr'].calls))

    def test_crossing_ninety_percent_during_stop_starts_grace_and_blocks_delete(self):
        t = torrent(progress=.89, state='downloading', downloaded=89, completed=89, amount_left=11, dlspeed=10)
        r, q = self.runner(t, apply=True)
        q.filemap[H][0]['progress'] = .89
        self.mature(r, t, rows(t, q.filemap[H]))
        r.apis['radarr'].queue = [{'id': 7, 'downloadId': H}]
        original = q.call
        def call(path, *a, **kw):
            result = original(path, *a, **kw)
            if path.endswith('/stop'):
                q.data[H].update(progress=.90, downloaded=90, completed=90, amount_left=10)
                q.filemap[H][0]['progress'] = .90
            return result
        q.call = call
        with self.assertRaises(C.Refused):
            r.run()
        self.assertIn(H, q.data)
        self.assertFalse(any(c[0].endswith('/delete') for c in q.calls))

    def test_restarted_or_changed_after_blocklist_is_not_deleted(self):
        for change in ('restart', 'bytes'):
            r, q = self.runner(torrent(), apply=True)
            self.mature(r, torrent())
            arr = r.apis['radarr']
            arr.queue = [{'id': 7, 'downloadId': H}]
            original = arr.call
            def call(path, *a, **kw):
                result = original(path, *a, **kw)
                if kw.get('method') == 'DELETE':
                    if change == 'restart':
                        q.data[H]['state'] = 'downloading'
                    else:
                        q.data[H]['downloaded'] += 1
                return result
            arr.call = call
            with self.assertRaises(C.Refused):
                r.run()
            self.assertFalse(any(c[0].endswith('/delete') for c in q.calls))
            # New independent fixture on next iteration; never clear a pending marker to retry.
            (self.home/'state.json').unlink()

    def test_retained_log_explains_missing_history_and_grace(self):
        r, _ = self.runner(torrent())
        r.run()
        kept = next(e for e in self.audit.records if e['event'] == 'retained')
        self.assertEqual(kept['reason'], 'insufficient_history')
        self.assertEqual(kept['window_seconds'], 0)
        self.assertEqual(kept['minimum_delta_percentage_points'], 5)

    def test_manager_failure_invalidates_daily_window_but_preserves_calendar_grace(self):
        t = torrent(progress=.95, downloaded=95, completed=95, amount_left=5)
        r, q = self.runner(t, apply=True)
        q.filemap[H][0]['progress'] = .95
        self.mature(r, t, rows(t, q.filemap[H]))
        r.state['observations'][H]['near_complete_since'] = NOW-7*86400
        r.apis['radarr'].queue = [{'id': 7, 'downloadId': H}]
        r.apis['radarr'].fail.add('/api/v3/system/status')
        r.run()
        rec = r.state['observations'][H]
        self.assertEqual(rec['near_complete_since'], NOW-7*86400)
        self.assertFalse(rec['healthy'])
        self.assertEqual(len(rec['samples']), 1)
        self.assertTrue(all(c[2] == 'GET' for c in q.calls))

    def test_active_transfer_also_requires_independent_connectivity(self):
        t = torrent(state='downloading', dlspeed=10)
        r, q = self.runner(t, apply=True)
        self.mature(r, t)
        r.connectivity = lambda: False
        r.run()
        self.assertFalse(r.state['observations'][H]['healthy'])
        self.assertTrue(all(c[2] == 'GET' for c in q.calls))

    def test_expired_grace_does_not_override_complete_media_pack_guard(self):
        t = torrent(progress=.95, downloaded=95, completed=95, amount_left=5)
        r, q = self.runner(t, apply=True)
        q.filemap[H] = [{**files()[0], 'progress': .95},
                       {'name': 'Example/complete.mkv', 'size': 100, 'priority': 0, 'progress': 1}]
        self.mature(r, t, rows(t, q.filemap[H]))
        r.state['observations'][H]['near_complete_since'] = NOW-7*86400
        r.run()
        self.assertTrue(all(c[2] == 'GET' for c in q.calls))
        self.assertIn('mixed_complete_media', [e.get('reason') for e in self.audit.records])

    def test_operator_paused_before_mutation_is_not_stopped_or_deleted_by_script(self):
        t = torrent()
        r, q = self.runner(t, apply=True)
        self.mature(r, t)
        q.data[H]['state'] = 'stoppedDL'
        with self.assertRaises(C.Refused):
            r.mutate(t, rows(t), 'stalled')
        self.assertTrue(all(c[2] == 'GET' for c in q.calls))

    def test_no_managed_queue_match_prevents_partial_deletion(self):
        t = torrent()
        r, q = self.runner(t, apply=True)
        self.mature(r, t)
        r.run()
        self.assertTrue(all(c[2] == 'GET' for c in q.calls))

    def test_global_connectivity_failure_resets_and_prevents_deletion(self):
        t = torrent()
        r, q = self.runner(t, apply=True)
        self.mature(r, t)
        r.connectivity = lambda: False
        r.run()
        self.assertEqual(r.state['observations'][H]['samples'][0]['time'], NOW)
        self.assertTrue(all(c[2] == 'GET' for c in q.calls))

    def test_keep_tag_and_forced_torrents_are_untouched(self):
        for t in (torrent(tags='other,cleanup-keep'), torrent(force_start=True)):
            r, q = self.runner(t, apply=True)
            r.run()
            self.assertTrue(all(c[2] == 'GET' for c in q.calls))

    def test_unknown_version_refuses_before_mutations(self):
        r, q = self.runner(torrent(), apply=True)
        q.version = b'v9.0.0'
        with self.assertRaisesRegex(C.Refused, 'unreviewed'):
            r.run()
        self.assertTrue(all(c[2] == 'GET' for c in q.calls))

    def test_shared_content_and_cross_seed_are_refused(self):
        t = torrent()
        r, q = self.runner(t)
        other = torrent(hash='b'*40, category='unmanaged')
        q.data[other['hash']] = other
        q.filemap[other['hash']] = files()
        with self.assertRaisesRegex(C.Refused, 'overlapping'):
            r.no_shared_payload(t, rows(t))

    def test_failed_mutation_stays_pending_and_is_never_automatically_retried(self):
        t = torrent(True)
        r, q = self.runner(t, apply=True)
        q.fail.add('/api/v2/torrents/delete')
        with patch.object(r, 'imported'), self.assertRaises(C.Refused):
            r.run()
        self.assertIn(H, r.state['pending'])
        before = len([c for c in q.calls if c[2] == 'POST'])
        with patch.object(r, 'imported'), self.assertRaises(C.Refused):
            r.run()
        self.assertEqual(before, len([c for c in q.calls if c[2] == 'POST']))

    def test_audit_failure_prevents_mutation(self):
        t = torrent(True)
        r, q = self.runner(t, apply=True)
        with patch.object(self.audit, 'emit', side_effect=C.Refused('audit_write_failed')):
            with self.assertRaises(C.Refused):
                r.mutate(t, rows(t), 'completed')
        self.assertTrue(all(c[2] == 'GET' for c in q.calls))

    def test_progress_between_snapshot_and_action_blocks_delete(self):
        t = torrent(True)
        r, q = self.runner(t, apply=True)
        q.data[H]['downloaded'] += 1
        with self.assertRaises(C.Refused):
            r.mutate(t, rows(t), 'completed')
        self.assertTrue(all(c[2] == 'GET' for c in q.calls))

    def test_complete_episode_appearing_after_stop_blocks_data_deletion(self):
        t = torrent()
        r, q = self.runner(t, apply=True)
        self.mature(r, t)
        r.apis['radarr'].queue = [{'id': 7, 'downloadId': H}]
        original_call = q.call
        def call(path, *a, **kw):
            value = original_call(path, *a, **kw)
            if path.endswith('/stop'):
                q.filemap[H][0]['progress'] = 1
            return value
        q.call = call
        with self.assertRaises(C.Refused):
            r.mutate(t, rows(t), 'stalled')
        self.assertFalse(any(c[0].endswith('/delete') for c in q.calls))
        self.assertIn(H, r.state['pending'])

    def test_action_cap(self):
        t = torrent(True)
        r, q = self.runner(t, apply=True)
        r.max_actions = 1
        other = torrent(True, hash='b'*40, content_path='/data/downloads/movies/Other/movie.mkv')
        q.data[other['hash']] = other
        q.filemap[other['hash']] = [{**files(True)[0], 'name': 'Other/movie.mkv'}]
        with patch.object(r, 'imported'):
            r.run()
        self.assertEqual(len([c for c in q.calls if c[0].endswith('/delete')]), 1)

    def test_independent_policy_selection(self):
        r, q = self.runner(torrent(True), apply=True, policy='stalled')
        with patch.object(r, 'imported') as imported:
            r.run()
        imported.assert_not_called()
        self.assertTrue(all(c[2] == 'GET' for c in q.calls))

    def test_state_missing_is_new_baseline_corrupt_state_refuses(self):
        r, _ = self.runner(torrent())
        self.assertFalse(r.state['observations'])
        p = self.home/'state.json'
        p.write_text('{broken')
        p.chmod(0o600)
        with self.assertRaises(ValueError):
            self.runner(torrent())

    def test_v1_migration_discards_old_clock_but_preserves_pending_and_requires_review(self):
        p = self.home/'state.json'
        pending = {H: {'action_id': 'synthetic-action', 'policy': 'stalled', 'time': NOW-1}}
        old = {'version': 1, 'observations': {H: {'since': NOW-100000}}, 'pending': pending}
        C.atomic_json(p, old)
        r, _ = self.runner()
        self.assertEqual(r.state, {'version': 2, 'observations': {}, 'pending': pending})
        with self.assertRaisesRegex(C.Refused, 'pending_action_requires_review'):
            r.run()
        saved = json.loads(p.read_text())
        self.assertEqual(saved['pending'], pending)
        self.assertEqual(saved['version'], 2)
        self.assertTrue(any(e['event'] == 'state_migrated' for e in self.audit.records))

    def test_unknown_state_version_is_not_silently_reset(self):
        C.atomic_json(self.home/'state.json', {'version': 99, 'observations': {}, 'pending': {}})
        with self.assertRaisesRegex(C.Refused, 'invalid_state'):
            self.runner(torrent())

    def test_v2_history_and_grace_survive_process_reload(self):
        t = torrent(progress=.95, downloaded=95, completed=95)
        r, _ = self.runner(t)
        self.mature(r, t, rows(t, [{**files()[0], 'progress': .95}]))
        r.state['observations'][H]['near_complete_since'] = NOW-3*86400
        r.save()
        again, _ = self.runner(t)
        self.assertEqual(again.state, r.state)
        self.assertFalse(again.migrated)

    def test_state_atomic_permissions_and_symlink_refusal(self):
        p = self.home/'state.json'
        C.atomic_json(p, {'observations': {}})
        self.assertEqual(p.stat().st_mode & 0o777, 0o600)
        target = self.home/'target'
        target.write_text('preserve')
        p.unlink()
        p.symlink_to(target)
        with self.assertRaises(C.Refused):
            C.atomic_json(p, {})
        self.assertEqual(target.read_text(), 'preserve')

    def test_private_file_rejects_public_permissions_and_hardlinks(self):
        p = self.home/'secret.json'
        p.write_text('{}')
        p.chmod(0o644)
        with self.assertRaises(C.Refused): C.private_file(p)
        p.chmod(0o600)
        (self.home/'alias').hardlink_to(p)
        with self.assertRaises(C.Refused): C.private_file(p)

    def test_systemd_readonly_root_credentials_are_not_ordinary_private_files(self):
        p = Path('/run/credentials/example.service/settings.json')
        s = SimpleNamespace(st_mode=stat.S_IFREG | 0o440, st_uid=0, st_gid=0, st_nlink=1)
        with patch.dict(os.environ, {'CREDENTIALS_DIRECTORY': str(p.parent)}), \
             patch.object(Path, 'lstat', return_value=s), patch.object(Path, 'is_symlink', return_value=False), \
             patch.object(os, 'statvfs', return_value=SimpleNamespace(f_flag=os.ST_RDONLY)):
            self.assertEqual(C.private_input(p), p)
            with self.assertRaises(C.Refused): C.private_file(p)

    def test_systemd_credential_requires_readonly_mount_and_restrictive_mode(self):
        p = Path('/run/credentials/example.service/settings.json')
        s = SimpleNamespace(st_mode=stat.S_IFREG | 0o440, st_uid=0, st_gid=0, st_nlink=1)
        with patch.dict(os.environ, {'CREDENTIALS_DIRECTORY': str(p.parent)}), \
             patch.object(Path, 'lstat', return_value=s), patch.object(Path, 'is_symlink', return_value=False):
            with patch.object(os, 'statvfs', return_value=SimpleNamespace(f_flag=0)):
                with self.assertRaisesRegex(C.Refused, 'unsafe_systemd_credential'): C.private_input(p)
            s.st_mode = stat.S_IFREG | 0o444
            with patch.object(os, 'statvfs', return_value=SimpleNamespace(f_flag=os.ST_RDONLY)):
                with self.assertRaisesRegex(C.Refused, 'unsafe_systemd_credential'): C.private_input(p)

    def test_spoofed_credential_directory_does_not_relax_regular_files(self):
        p = self.home/'settings.json'; p.write_text('{}'); p.chmod(0o440)
        with patch.dict(os.environ, {'CREDENTIALS_DIRECTORY': str(self.home)}):
            with self.assertRaises(C.Refused): C.private_input(p)
        p.chmod(0o600)
        self.assertEqual(C.private_input(p), p)

    def test_storage_guard_distinguishes_host_rw_from_isolated_ro(self):
        credential = MagicMock()
        credential.read_text.return_value = json.dumps({'filesystem_uuid': 'example-fs'})
        def mount(mode='rw', uuid='example-fs'):
            return SimpleNamespace(stdout=json.dumps({'filesystems': [{'target': '/data', 'fstype': 'ext4',
                'uuid': uuid, 'options': mode + ',relatime'}]}))
        with patch.object(C, 'private_input', return_value=credential), \
             patch.dict(os.environ, {}, clear=True), patch.object(C.subprocess, 'run', return_value=mount()):
            C.check_storage()
            with patch.object(C.subprocess, 'run', return_value=mount('ro')):
                with self.assertRaisesRegex(C.Refused, 'storage_guard_failed'): C.check_storage()
        with patch.object(C, 'private_input', return_value=credential), \
             patch.dict(os.environ, {'CREDENTIALS_DIRECTORY': '/run/credentials/example.service'}), \
             patch.object(C.subprocess, 'run', return_value=mount('ro')), \
             patch.object(os, 'statvfs', return_value=SimpleNamespace(f_flag=os.ST_RDONLY)):
            C.check_storage()
            with patch.object(C.subprocess, 'run', return_value=mount('ro', 'wrong-fs')):
                with self.assertRaisesRegex(C.Refused, 'storage_guard_failed'): C.check_storage()

    def test_audit_records_intent_outcome_mode_and_rotates(self):
        d = self.home/'logs'
        d.mkdir(mode=0o700)
        audit = C.Audit(d, apply=False, max_bytes=450, backups=2)
        for _ in range(8): audit.emit('candidate', torrent(), reason='test_only')
        audit.close()
        self.assertLessEqual(len(list(d.iterdir())), 3)
        lines = [json.loads(line) for p in d.iterdir() for line in p.read_text().splitlines()]
        self.assertTrue(all(r['mode'] == 'dry-run' and r['run_id'] and r['time'] for r in lines))
        self.assertTrue(all((p.stat().st_mode & 0o777) == 0o600 for p in d.iterdir()))

    def test_audit_rejects_symlink_without_touching_target(self):
        d = self.home/'logs'
        d.mkdir(mode=0o700)
        target = self.home/'target'
        target.write_text('preserve')
        (d/'audit.jsonl').symlink_to(target)
        with self.assertRaises(C.Refused): C.Audit(d)
        self.assertEqual(target.read_text(), 'preserve')

    def test_arr_pagination_never_assumes_one_page_or_truncates(self):
        r, _ = self.runner()
        api = r.apis['radarr']
        with patch.object(api, 'call', side_effect=[{'records': [1], 'totalRecords': 2},
                                                  {'records': [2], 'totalRecords': 2}]):
            self.assertEqual(r.page('radarr', '/api/v3/history'), [1, 2])
        with patch.object(api, 'call', side_effect=[{'records': [1], 'totalRecords': 2},
                                                  {'records': [], 'totalRecords': 2}]):
            with self.assertRaises(C.Refused): r.page('radarr', '/api/v3/history')

    def test_jellyfin_exact_paths_pagination_not_title_matching(self):
        r, _ = self.runner()
        api = r.apis['jellyfin']
        api.items = [{'Name': 'Same title', 'Path': '/media/movies/Wrong/movie.mkv', 'IsFolder': False}]
        self.assertEqual(r.jellyfin_paths(), {'/media/movies/Wrong/movie.mkv'})

    def test_imported_requires_every_source_hash_history_current_hardlink_and_jellyfin(self):
        t = torrent(True)
        r, _ = self.runner(t)
        src, dst = '/data/downloads/movies/Example/movie.mkv', '/data/media/movies/Example/movie.mkv'
        event = {'downloadId': H.upper(), 'eventType': 'downloadFolderImported',
                 'date': '2033-05-18T01:00:00Z', 'data': {'droppedPath': src, 'importedPath': dst}}
        # Fixture date must postdate added_on but need not rely on actual wall-clock.
        event['date'] = C.dt.datetime.fromtimestamp(t['added_on']+10, C.dt.timezone.utc).isoformat()
        r.apis['radarr'].history = [event]
        r.apis['jellyfin'].items = [{'Path': '/media/movies/Example/movie.mkv'}]
        fake_stat = type('Stat', (), {'st_size': 100, 'st_dev': 1, 'st_ino': 20})()
        with patch.object(C, 'checked_path', side_effect=lambda p, *a, **k: Path(p)), patch.object(Path, 'stat', return_value=fake_stat):
            r.imported(t, rows(t))
            r.jelly_paths = set()
            with self.assertRaisesRegex(C.Refused, 'jellyfin_discovery_pending'):
                r.imported(t, rows(t))
            r.apis['radarr'].history[0]['downloadId'] = 'b'*40
            with self.assertRaisesRegex(C.Refused, 'import_history_missing'):
                r.imported(t, rows(t))

    def test_old_import_history_cannot_validate_readded_torrent(self):
        t = torrent(True)
        r, _ = self.runner(t)
        r.apis['radarr'].history = [{'downloadId': H, 'eventType': 'downloadFolderImported',
            'date': C.dt.datetime.fromtimestamp(t['added_on']-1, C.dt.timezone.utc).isoformat(), 'data': {}}]
        with self.assertRaisesRegex(C.Refused, 'import_history_missing'):
            r.imported(t, rows(t))

    def test_config_rejects_public_urls_embedded_credentials_and_placeholders(self):
        # Synthesize an invalid URL from explicitly fake fields; no credential-bearing URL fixture.
        userinfo = ':'.join(('example-user', 'not-real'))
        embedded = C.urllib.parse.urlunsplit(('http', userinfo + '@127.0.0.1', '', '', ''))
        for url in (embedded, 'http://127.0.0.1/?token=x', 'file:///etc/passwd'):
            with self.assertRaises(C.Refused): C.validate_url(url)
        p = self.home/'credentials.json'
        p.write_text((MODULE/'config/torrent-cleanup/credentials.json.example').read_text())
        p.chmod(0o600)
        with self.assertRaises(C.Refused): C.load_config(p)

    def test_modern_qbit_cookie_and_authenticated_probe(self):
        api = C.API({'url': 'http://127.0.0.1:8080', 'username': 'example', 'password': 'not-real'}, 'qbittorrent')
        api.jar = [SimpleNamespace(name='QBT_SID_8080')]
        with patch.object(api, 'call', side_effect=[b'', b'v5.2.4']) as call:
            api.login()
            self.assertEqual(call.call_count, 2)
        with patch.object(api, 'call', side_effect=[b'', b'not-authenticated']):
            with self.assertRaises(C.Refused): api.login()

    def test_jellyfin_uses_modern_authorization_not_legacy_token(self):
        api = C.API({'url': 'http://127.0.0.1:8096', 'api_key': 'example-only'}, 'jellyfin')
        response = MagicMock()
        response.__enter__.return_value.status = 200
        response.__enter__.return_value.read.return_value = b'{}'
        with patch.object(api.client, 'open', return_value=response) as opened:
            api.call('/Items')
        request = opened.call_args.args[0]
        self.assertIn('MediaBrowser ', request.get_header('Authorization'))
        self.assertIn('Token="example-only"', request.get_header('Authorization'))
        self.assertIsNone(request.get_header('X-emby-token'))

    def test_redirects_and_request_errors_do_not_leak_response_secrets(self):
        with self.assertRaisesRegex(C.Refused, 'http_redirect_refused'):
            C.NoRedirect().redirect_request(None)
        api = C.API({'url': 'http://127.0.0.1:8096', 'api_key': 'example-only'}, 'jellyfin')
        with patch.object(api.client, 'open', side_effect=OSError('secret-content')):
            with self.assertRaisesRegex(C.Refused, '^api_request_failed$'):
                api.call('/Items')

    def test_service_is_nonroot_readonly_bounded_and_dry_run(self):
        service = (MODULE/'config/torrent-cleanup/torrent-cleanup.service').read_text()
        timer = (MODULE/'config/torrent-cleanup/torrent-cleanup.timer').read_text()
        for setting in ('DynamicUser=yes', 'SupplementaryGroups=media', 'ReadOnlyPaths=/data', 'LoadCredential=',
                        'ProtectSystem=strict', 'TimeoutStartSec=10min', 'MemoryMax=192M', 'NoNewPrivileges=yes',
                        'ExecStartPre=+/usr/local/sbin/check-media-storage'):
            self.assertIn(setting, service)
        self.assertNotIn('--apply', service)
        self.assertIn('OnCalendar=*-*-* 00,06,12,18:00:00', timer)
        self.assertIn('Persistent=yes', timer)
        self.assertNotIn('RemainAfterExit', service)

    def test_module_diagram_explains_runtime_rules_without_temporary_installers(self):
        readme = (MODULE/'README.md').read_text()
        diagrams = [part.split('```', 1)[0] for part in readme.split('```mermaid\n')[1:]]
        self.assertGreaterEqual(len(diagrams), 2)
        diagram = next(d for d in diagrams if 'torrent-cleanup.py' in d)
        for label in ('torrent-cleanup.timer: cada 6 h', 'check-media-storage', 'torrent-cleanup.service',
                      'state.json', 'audit.jsonl', 'Completos: 100% y al menos 1 h',
                      '5 puntos en 24 h observadas', '90%: al menos 7 días',
                      'conservar archivos', 'borrar parciales', 'sin buscar reemplazo', 'revalidar', 'pending'):
            self.assertIn(label, diagram)
        for flow in ('cleanupTimer --> mountGuard', 'cleanupJob --> completeRule', 'cleanupJob --> slowRule',
                     'completeRule --> entryOnly', 'slowRule --> partialGuards', 'blockRelease --> deletePartial'):
            self.assertIn(flow, diagram)
        for private in ('install-current-site', 'upgrade-current-site', 'activate-current-site'):
            self.assertNotIn(private, diagram)
        self.assertIn('docs/torrent-cleanup.md', readme)
        self.assertIn('no que todos los casos hayan sucedido', readme)

    def test_help_does_not_contact_services(self):
        r = subprocess.run([sys.executable, str(SCRIPT), '--help'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn('--apply', r.stdout)
        self.assertIn('--policy', r.stdout)


if __name__ == '__main__':
    unittest.main()
