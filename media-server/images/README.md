# Media Server Images

User-provided screenshots supporting the [Setup Guide](../docs/setup-guide.md), [Jellyfin Service Guide](../docs/jellyfin.md), [Prowlarr Service Guide](../docs/prowlarr.md) and [Radarr Service Guide](../docs/radarr.md).

- Installer screenshots: QEMU Agent, disk options, Debian software selection and GRUB.
- [Jellyfin initial administrator](jellyfin-initial-admin-account.png): completed `jellyfin-admin` username and masked password fields, before pressing **Next**. The same username is used as the guide's concrete example; no password value is recorded.
- [Jellyfin Shows library before review](jellyfin-shows-library-options-before-review.png): historical review evidence only; includes uncorrected options and must **not** be used as a configuration example.

Screenshots document reviewed UI choices, not deployment or playback acceptance by themselves. Preserve originals; review future screenshots for visible passwords, addresses and identifiers before adding them to public documentation.

- [Jellyfin Shows reviewed form](jellyfin-shows-library-reviewed.png): **primary approved configuration reference**, with `/media/tv`, English metadata, Argentina and save-subtitles-to-media disabled, before pressing **OK**. Embedded with the full settings table in [Verified Shows Configuration](../docs/jellyfin.md#verified-shows-configuration).
- [Jellyfin Movies reviewed form](jellyfin-movies-library-reviewed.png): **primary approved Movies configuration reference**, with `/media/movies`, English metadata, Argentina and media-folder writes disabled, before pressing **OK**. Embedded with the exact options in [Verified Movies Configuration](../docs/jellyfin.md#verified-movies-configuration).
- [Configured libraries overview](jellyfin-libraries-configured.png): wizard overview confirming `Movies` at `/media/movies` and `Shows` at `/media/tv`, before **Next**; does not imply completed setup or playback.

- [Global metadata reviewed](jellyfin-global-metadata-reviewed.png): approved `English` language and `Argentina` region before **Next**, embedded in [Global Metadata Defaults](../docs/jellyfin.md#global-metadata-defaults).

- [Remote access enabled](jellyfin-remote-access-enabled.png): confirmed user choice to leave the remote-connections permission enabled; no automatic WAN/router publication.

- [Prowlarr initial authentication reviewed](prowlarr-initial-authentication-reviewed.png): **approved first-run reference**, Forms (Login Page), Enabled, `prowlarr-admin`, masked password/confirmation and empty Allowed Hosts, **before Save**. Embedded in [Reviewed Authentication Form](../docs/prowlarr.md#reviewed-authentication-form); not evidence of saved settings or successful login.

- [Prowlarr empty indexers after authentication](prowlarr-indexers-empty-after-authentication.png): user reached **Indexers** after **Save**, no sources configured, **Add New Indexer** is the next action. Embedded in [Saved Authentication and First Indexers Screen](../docs/prowlarr.md#saved-authentication-and-first-indexers-screen).

- [Prowlarr unfiltered indexer catalog](prowlarr-indexer-catalog-unfiltered.png): catalogue screenshot with657 definitions before selecting any; illustrates **Search indexers** and **Filters**, not an approved/activated provider list. See [shortlist research](../docs/prowlarr.md#indexer-shortlist-research--2026-10-16).

- [1337x form before test](prowlarr-1337x-form-before-test.png): user selected1337x; **Base Url is still empty**, Test/Save not confirmed. Review evidence, not approved working indexer configuration. See [1337x Form Review](../docs/prowlarr.md#1337x-form-review--before-test).

- [1337x failed-save attempt](prowlarr-1337x-cloudflare-attempt.png): Base Url selected; user reports **Cloudflare blocked Save**. The error text is not visible in the image. Diagnostic evidence only, **not a working configuration**; read-only API check confirmed zero saved indexers. See [Cloudflare block](../docs/prowlarr.md#1337x-save-attempt--cloudflare-blocked).

- [Knaben reviewed before Save](prowlarr-knaben-reviewed-before-save.png): **approved field reference**, Enable ON, Redirect OFF, Standard, `https://knaben.org/`, Seed Ratio and Tags empty. User reports successful Test, but its checkmark is not visible in this image. **Before Save**; the later saved-list confirmation is documented separately below. See [Knaben configuration](../docs/prowlarr.md#knaben-reviewed-configuration--test-passed-save-pending).

- [Knaben saved in Indexers](prowlarr-knaben-saved-indexers.png): **saved/enabled UI confirmation**, one indexer, Torrent/Public, priority25, Standard. Does not prove manager integration or a completed download. See [Knaben saved](../docs/prowlarr.md#knaben-saved-and-enabled).

- [EZTV Cloudflare attempt](prowlarr-eztv-cloudflare-attempt.png): visible red error for **eztv1.xyz**, not proof that every EZTV URL is blocked. Diagnostic evidence, **not a working configuration**; later read-only API check confirms only Knaben saved. See [EZTV attempt](../docs/prowlarr.md#eztv-attempt--cloudflare-at-eztv1xyz).

- [Radarr initial account before setup](radarr-initial-authentication-before-setup.png): historical native form, **Method None and account fields empty**; not an approved configuration. Kept collapsed in the guide to avoid confusing it with the completed reference below.

- [Radarr initial authentication reviewed](radarr-initial-authentication-reviewed.png): **primary approved field reference before Save**, Forms(LoginPage), Enabled, `radarr-admin`, masked password/confirmation and empty AllowedHosts. Does not confirm saved settings or login. See [Reviewed Authentication Form](../docs/radarr.md#reviewed-authentication-form).

- [Radarr Movies after authentication](radarr-movies-empty-after-authentication.png): user reached Movies after Save; empty library and System3 are expected pending content/integration. Later read-only check confirms Forms/Enabled, anonymous302/login and API401; the three health messages concern RSS/search indexers and missing download client. See [Saved account](../docs/radarr.md#saved-account-and-first-movies-screen).

- [Radarr movie root folder configured](radarr-root-folder-configured.png): **approved saved root reference**, `/data/media/movies`,1.8TiB free,0 unmapped and No Changes. Later read-only API confirms one accessible root, no movies/indexers/clients. Other visible settings were left unchanged, not adopted as a final naming policy; no import/hardlink/playback acceptance implied. See [Configured Root Folder Reference](../docs/radarr.md#configured-root-folder-reference).

- [Prowlarr Add Application Radarr before setup](prowlarr-radarr-application-before-setup.png): initial form only, Name Radarr, Full Sync, empty Tags/API Key and both URLs still `localhost`. **Not a working or final configuration**; URLs must be replaced for the separate-container design. See [Prowlarr → Radarr instructions](../docs/radarr.md#72-prowlarr--radarr).

The original completed Radarr application screenshot and the later partially pixelated attachment were **not copied here**. Never publish an original secret-bearing image behind a cosmetic overlay.

- [Prowlarr Radarr reviewed application — fully redacted reference](prowlarr-radarr-application-reviewed-redacted.png): **derived visual reference edited with image_gen**, based on the user's censored attachment. Full opaque redactions cover API Key and hosts; ports9696/7878, Name Radarr, Full Sync and empty Tags remain visible. Not pixel-exact evidence or confirmation of Save/sync; successful Test remains user-reported. See [Reviewed Application Form](../docs/radarr.md#reviewed-application-form--redacted-reference). The later saved Apps evidence is documented below.
  - [Redaction method and complete prompt](prowlarr-radarr-application-reviewed-redacted.json); no source secret or private path included.

- [Prowlarr Radarr saved application](prowlarr-radarr-application-saved.png): **original secret-free screenshot after Save**, Radarr/Full Sync and Standard profile with RSS, Automatic Search and Interactive Search. Later read-only API confirms Knaben (Prowlarr) registered in Radarr with those functions enabled; only DownloadClientCheck remains. No real download/import/playback accepted. See [saved application and verified sync](../docs/radarr.md#saved-application-and-verified-knaben-synchronization).

- [Radarr qBittorrent client before setup](radarr-qbittorrent-client-before-setup.png): original initial form, **not approved final settings**. Host localhost, Category radarr, empty credentials and Remove Completed/Failed ON need review/correction. See [field-by-field instructions](../docs/radarr.md#73-radarr--qbittorrent); Test/Save were unconfirmed at that initial stage. The approved and saved references below supersede it for configuration.

- [Radarr qBittorrent reviewed form — Test passed](radarr-qbittorrent-client-reviewed-test-passed.png): **original, byte-identical user screenshot**, API Key empty, password masked, admin/movies, SSL and both Remove OFF, green Test before Save. Owner requested inclusion; site-specific LAN IP is visible, unlike reusable text templates. No visible API key/password value. See [approved fields and scope](../docs/radarr.md#reviewed-qbittorrent-client-form--test-passed).
- [Radarr qBittorrent saved client](radarr-qbittorrent-client-saved.png): **original, byte-identical user screenshot after Save**, one qBittorrent Enabled card, No Changes and empty Remote Path Mappings. Confirms saved client by UI, not post-save API health or real download/import/playback. See [saved client](../docs/radarr.md#saved-qbittorrent-client--ui-confirmation).
