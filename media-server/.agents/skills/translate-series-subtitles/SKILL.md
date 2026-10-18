---
name: translate-series-subtitles
description: Translate an existing season's English SRT files into Spanish using Google Free on syedgakbar.com/projects/dst, in verified batches of at most 20, then optionally install matching Jellyfin sidecars. Use for this media-server subtitle workflow, not general text translation, subtitle-provider searches, or video transcription.
---

# Translate Series Subtitles

Use the website chosen by the owner, not a different translator or paid model.
The skill's canonical folder belongs inside the `media-server` module. Its Python
helper finds that module by locating `scripts/extract-embedded-subtitles.py` in
its ancestors. Run on the administration Mac/Linux host with Python 3.10+.

## Inputs and boundaries

- Resolve one season, its English export directory, and a fresh run directory
  beneath the module's **ignored `exports/`**. Keep source and run directories
  separate. Do not put subtitle content, archives, reports or screenshots in Git.
- Reuse English exports when available. Otherwise use the existing module
  extractor with explicit source/season and separate output; inspect language
  metadata instead of guessing unknown or bitmap subtitles.
- Compare the English set with the extractor report or selected season's videos
  before promising a complete season. The helper's expected count covers supplied
  source files, not an editorial episode count; combined episodes remain one SRT.
- Upload only the requested SRT files to `https://www.syedgakbar.com/projects/dst`
  and its Google translation UI. The workflow does not authorize videos, private
  files, credentials, sign-in, purchases, premium providers or unrelated uploads.
- If the user has not identified the season/source, ask for that information.
  Creating a skill is not authorization to translate every series in a library.

## Prepare immutable batches

Let `HELPER` be this skill's `scripts/subtitle_batches.py`. Commands shown below
use shell variables resolved from the current task, never literal placeholders.
Prefix shell commands with `rtk` in this repository.

```sh
rtk proxy python3 "$HELPER" prepare --source "$ENGLISH_SEASON" --run "$RUN"
rtk proxy python3 "$HELPER" prepare --source "$ENGLISH_SEASON" --run "$RUN" --apply
rtk proxy python3 "$HELPER" status --run "$RUN"
```

The manifest freezes inputs and partitions **all** files: 21 becomes 20+1,
22 becomes 20+2, 41 becomes 20+20+1. `status` returns file paths, counts and
completion without dialogue. Resume already accepted batches; do not recreate
an existing run or override partial artifacts.

## Browser translation: one new document per batch

Use available CUA browser tools. Before the first real translation in a new
environment, test with non-sensitive synthetic SRT files. If upload/download is
not supported, stop and explain the missing capability; a skill cannot add it.

1. For **each** incomplete batch, create a **fresh tab/document** at the website.
   **Do not use New to reuse a translated document between batches.** Its UI can
   show only new files while Save All still includes entries from the old ZIP.
2. Observe the current upload zone, start the documented browser `filechooser`
   event, click that zone and use `setFiles` with exactly the manifest's frozen
   `input_files`. No OS drag/drop automation or hidden application calls needed.
3. Wait for upload completion. Check the visible filename selector's options
   against the exact batch set (not just a count). For a singleton, check its
   displayed filename. If files are missing or extra, stop before Translate.
4. Verify **Google (Free)** and **Spanish / Español** (language value `es`) in
   the observed UI, then click Translate. Google may translate page labels too.
   Prefer accessible controls when ads/translated layouts interfere with clicks.
5. Check only progress, success/error and save controls. Wait between meaningful
   observations, typically 15–30 seconds, rather than dumping subtitle tables or
   polling every second. A request for payment/sign-in, quota, CAPTCHA, or no
   progress for ten minutes stops this batch. Do not bypass restrictions, switch
   providers or repeatedly restart translations. A technical UI retry may use
   one fresh tab; keep the failed artifacts for inspection.
6. On success, capture a browser **download** event before clicking **Save All**.
   For a singleton use **Save As**, which returns one SRT instead of a ZIP.
   Let the event return, then request its `path()` in a separate tool call;
   awaiting both in one call caused long waits in the tested IAB environment.
   Capture the actual download path; do not guess a name or take the newest
   unrelated file from Downloads. Bring this task's generated download under
   the module's working directory, respecting filesystem permissions.
7. Validate before moving to the next batch:

   ```sh
   rtk proxy python3 "$HELPER" accept --run "$RUN" --batch "$BATCH" --download "$DOWNLOAD"
   rtk proxy python3 "$HELPER" accept --run "$RUN" --batch "$BATCH" --download "$DOWNLOAD" --apply
   ```

   The helper preserves the download and requires an exact set of flat `.es.srt`
   names, valid UTF-8/nonempty cues, unchanged numbering and **every timestamp**.
   It rejects ZIP traversal, symlinks, oversized data, extra/missing/duplicate
   files and entirely unchanged dialogue. Never silently filter a stale ZIP.
   Counts of unchanged individual cues are in the receipt for review; valid
   formatting is **not** proof of complete or high-quality Spanish translation.

## Complete, then optionally install

`status --run "$RUN"` must report `complete: true`, with expected and validated
counts equal across **every** batch. A website success banner is insufficient.
Record a screenshot of the successful browser result as private proof, not a
generated image or public per-series session log. Close only this task's tabs.

Only if the user requested installation into a specific library season:

```sh
rtk proxy python3 "$HELPER" install --run "$RUN" --library "$LIBRARY_SEASON"
rtk proxy python3 "$HELPER" install --run "$RUN" --library "$LIBRARY_SEASON" --apply
```

The helper checks all mappings first: **current complete video basename +
`.es.srt`**, not just an episode number. Changed/ambiguous video names or a
different existing Spanish SRT stop installation; identical copies are skipped.
English originals and videos stay untouched. Atomic publication requires
same-directory hardlink support; do not change filesystem permissions to force it.
If a multi-file install is interrupted, completed sidecars remain; rerun after
review, without deleting existing work. Do not promise a season-wide transaction.

If the Mac's SMB mount rejects `os.link` with `Operation not supported`, inspect
the season for partial copies before retrying. With existing authorized SSH
access, run the **same helper** on the server's native filesystem instead. Transfer
only the helper, extractor (for module discovery), manifest, frozen inputs,
accepted outputs and receipts into a temporary module with the same layout;
never copy credentials or the whole checkout. Recheck hashes and complete status,
then preview/apply as the existing media identity that Jellyfin can read. Keep
the no-overwrite publication unchanged, verify video metadata and installed
hashes, and remove only this task's remote staging after success. The helper does
not automate this SSH transport; unavailable authorized access is a blocker.

Jellyfin can discover sidecars asynchronously. Verify Spanish selection/delivery
when existing access permits; refresh only affected items if necessary, never
restart services or rebuild libraries. Report what is actually checked and ask
the user to confirm playback. Technical validation does not replace visual review.
