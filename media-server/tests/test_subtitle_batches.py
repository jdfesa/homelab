"""Deterministic synthetic tests; no network, browsers or real libraries."""
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
from unittest.mock import patch
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / '.agents/skills/translate-series-subtitles/scripts/subtitle_batches.py'
SPEC = importlib.util.spec_from_file_location('subtitle_batches', SCRIPT)
B = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(B)
EN = b'1\n00:00:01,250 --> 00:00:03,000\nGood morning.\n\n2\n00:00:05,000 --> 00:00:07,500\nThe library is open.\n'
ES = EN.replace(b'Good morning.', b'Buenos dias.').replace(b'The library is open.', b'La biblioteca esta abierta.')


class SubtitleBatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.module = self.root / 'module'
        (self.module / 'exports').mkdir(parents=True)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.run = self.module / 'exports/run'
        self.patch = patch.object(B, 'module_root', return_value=self.module)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def prepare(self, count=2):
        for i in range(1,count+1):
            (self.source / f'Series - S01E{i:02d}.en.srt').write_bytes(EN)
        return B.prepare(self.source, self.run, True)

    def archive(self, batch=1, change=None):
        manifest = json.loads((self.run / 'manifest.json').read_text())
        members = [(e['output_name'], ES) for e in manifest['batches'][batch-1]['files']]
        if change:
            members = change(members)
        p = self.root / f'batch-{batch}.zip'
        with warnings.catch_warnings(), zipfile.ZipFile(p,'w') as z:
            warnings.simplefilter('ignore', UserWarning)
            for name, raw in members:
                z.writestr(name,raw)
        return p

    def test_partition_never_drops_remaining_files(self):
        for count, expected in [(1,[1]),(20,[20]),(21,[20,1]),(22,[20,2]),(40,[20,20]),(41,[20,20,1])]:
            with self.subTest(count=count), tempfile.TemporaryDirectory(dir=self.root) as temp:
                source=Path(temp)/'source';source.mkdir()
                for i in range(count): (source/f'Series - S01E{i+1:02d}.en.srt').write_bytes(EN)
                run=self.module/'exports'/str(count)
                result=B.prepare(source,run,True)
                self.assertEqual(result['batch_sizes'],expected)
                self.assertEqual(B.status(run)['expected'],count)

    def test_preview_writes_nothing_and_refuses_oversized_batch(self):
        (self.source/'Series - S01E01.en.srt').write_bytes(EN)
        self.assertEqual(B.prepare(self.source,self.run)['files'],1)
        self.assertFalse(self.run.exists())
        for value in (0,21):
            with self.assertRaises(ValueError): B.prepare(self.source,self.run,batch_size=value)

    def test_working_directory_must_be_inside_module_exports(self):
        with self.assertRaises(ValueError): B.local_run(self.root/'outside')
        alias=self.module/'exports/alias';alias.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError): B.local_run(alias/'run')

    def test_invalid_source_and_symlinks_are_rejected(self):
        p=self.source/'Series - S01E01.en.srt';p.write_bytes(b'invalid')
        with self.assertRaises(ValueError): B.prepare(self.source,self.run,True)
        p.unlink();p.symlink_to(self.root/'missing')
        with self.assertRaises(ValueError): B.prepare(self.source,self.run,True)

    def test_resume_uses_frozen_inputs_not_overwritten_originals(self):
        self.prepare()
        for p in self.source.iterdir(): p.write_bytes(b'later edit')
        B.accept(self.run,1,self.archive(),True)
        self.assertTrue(B.status(self.run)['complete'])
        self.assertTrue(all(p.read_bytes()==b'later edit' for p in self.source.iterdir()))

    def test_frozen_input_tampering_and_manifest_symlink_fail(self):
        self.prepare()
        first=next((self.run/'batch-001/input').iterdir()); first.write_bytes(b'changed')
        with self.assertRaises(ValueError): B.status(self.run)
        first.write_bytes(EN)
        manifest=self.run/'manifest.json'; stored=manifest.read_bytes(); manifest.unlink()
        other=self.root/'external.json';other.write_bytes(stored);manifest.symlink_to(other)
        with self.assertRaises(ValueError): B.status(self.run)

    def test_batch_completion_requires_every_batch(self):
        self.prepare(22)
        B.accept(self.run,1,self.archive(1),True)
        self.assertEqual(B.status(self.run)['validated'],20)
        self.assertFalse(B.status(self.run)['complete'])
        B.accept(self.run,2,self.archive(2),True)
        self.assertTrue(B.status(self.run)['complete'])
        self.assertEqual(B.status(self.run)['validated'],22)

    def test_stale_previous_batch_entries_are_rejected(self):
        self.prepare(22)
        manifest=json.loads((self.run/'manifest.json').read_text())
        stale=[(e['output_name'],ES) for e in manifest['batches'][0]['files'][2:]]
        download=self.archive(2,change=lambda current:current+stale)
        with self.assertRaises(ValueError): B.accept(self.run,2,download,True)
        self.assertFalse((self.run/'batch-002/output').exists())

    def test_unicode_normalization_preserves_filename_mapping(self):
        import unicodedata
        source=self.source/'Series - S01E01 - Cafe\u0301.en.srt';source.write_bytes(EN)
        B.prepare(self.source,self.run,True)
        download=self.archive(change=lambda members:[(unicodedata.normalize('NFC',name),raw) for name,raw in members])
        B.accept(self.run,1,download,True)
        self.assertTrue(B.status(self.run)['complete'])

    def test_accept_preview_and_second_accept_preserve_outputs(self):
        self.prepare()
        z=self.archive()
        B.accept(self.run,1,z)
        self.assertFalse((self.run/'batch-001/output').exists())
        B.accept(self.run,1,z,True)
        before=(self.run/'batch-001/receipt.json').read_bytes()
        with self.assertRaises(FileExistsError): B.accept(self.run,1,z,True)
        self.assertEqual((self.run/'batch-001/receipt.json').read_bytes(),before)

    def test_missing_extra_duplicate_and_unsafe_zip_names_rejected(self):
        self.prepare()
        transforms=[lambda m:m[:-1],lambda m:m+[('Other.es.srt',ES)],lambda m:m+[m[0]],
                    lambda m:[('../escape.srt',ES)],lambda m:[('/absolute.srt',ES)],
                    lambda m:[('folder\\escape.srt',ES)],lambda m:[('nested/name.srt',ES)]]
        for change in transforms:
            with self.subTest(change=change), self.assertRaises(ValueError):
                B.accept(self.run,1,self.archive(change=change),True)
        self.assertFalse((self.run/'batch-001/output').exists())

    def test_symlink_and_oversized_zip_members_rejected(self):
        self.prepare()
        z=self.archive()
        with zipfile.ZipFile(z,'w') as archive:
            info=zipfile.ZipInfo('Series - S01E01.es.srt');info.create_system=3
            info.external_attr=(stat.S_IFLNK|0o777)<<16;archive.writestr(info,b'/etc/passwd')
        with self.assertRaises(ValueError): B.accept(self.run,1,z,True)
        z=self.archive()
        with patch.object(B,'MAX_FILE',10),self.assertRaises(ValueError): B.accept(self.run,1,z,True)

    def test_timestamp_numbering_empty_invalid_encoding_and_unchanged_fail(self):
        self.prepare()
        for bad in [ES.replace(b'00:00:03,000',b'00:00:04,000'),ES.replace(b'\n\n2\n',b'\n\n3\n'),
                    ES.replace(b'Buenos dias.',b''), b'\xff', EN]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                B.accept(self.run,1,self.archive(change=lambda m:[(name,bad) for name,_ in m]),True)
        self.assertFalse((self.run/'batch-001/output').exists())

    def test_singleton_download_and_utf8_bom_crlf(self):
        self.prepare(1)
        download=self.root/'Series - S01E01.es.srt';download.write_bytes(b'\xef\xbb\xbf'+ES.replace(b'\n',b'\r\n'))
        B.accept(self.run,1,download,True)
        self.assertTrue(B.status(self.run)['complete'])

    def test_singleton_must_keep_the_expected_spanish_filename(self):
        self.prepare(1)
        other=self.root/'Other.es.srt';other.write_bytes(ES)
        with self.assertRaises(ValueError): B.accept(self.run,1,other,True)
        self.assertFalse((self.run/'batch-001/output').exists())

    def test_modified_or_missing_accepted_file_does_not_remain_complete(self):
        self.prepare();B.accept(self.run,1,self.archive(),True)
        first=next((self.run/'batch-001/output').iterdir());first.write_bytes(b'changed')
        with self.assertRaises(ValueError): B.status(self.run)

    def test_install_requires_complete_run_and_exact_video_names(self):
        self.prepare()
        library=self.root/'library';library.mkdir()
        with self.assertRaises(ValueError): B.install(self.run,library,True)
        B.accept(self.run,1,self.archive(),True)
        with self.assertRaises(ValueError): B.install(self.run,library,True)
        self.assertFalse(list(library.glob('*.srt')))

    def test_install_dry_run_and_idempotence_preserve_videos(self):
        self.prepare();B.accept(self.run,1,self.archive(),True)
        library=self.root/'library';library.mkdir()
        for path in self.source.glob('*.en.srt'):
            (library/(path.name[:-len('.en.srt')]+'.mkv')).write_bytes(b'video fixture')
        self.assertEqual(B.install(self.run,library)['new'],2)
        self.assertFalse(list(library.glob('*.srt')))
        self.assertEqual(B.install(self.run,library,True)['new'],2)
        self.assertEqual(B.install(self.run,library,True)['existing_identical'],2)
        self.assertTrue(all(p.read_bytes()==b'video fixture' for p in library.glob('*.mkv')))

    def test_existing_spanish_conflict_prevents_entire_install(self):
        self.prepare();B.accept(self.run,1,self.archive(),True)
        library=self.root/'library';library.mkdir()
        for p in self.source.iterdir(): (library/(p.name[:-len('.en.srt')]+'.mkv')).write_bytes(b'fixture')
        existing=library/'Series - S01E02.es.srt';existing.write_bytes(b'owner translation')
        with self.assertRaises(FileExistsError): B.install(self.run,library,True)
        self.assertEqual(existing.read_bytes(),b'owner translation')
        self.assertEqual(len(list(library.glob('*.srt'))),1)

    def test_publish_collision_never_overwrites_or_leaves_staging(self):
        target=self.root/'example.srt';target.write_bytes(b'existing')
        with self.assertRaises(FileExistsError): B.publish(target,ES)
        self.assertEqual(target.read_bytes(),b'existing')
        self.assertFalse(list(self.root.glob('.subtitle-*')))


if __name__=='__main__': unittest.main()
