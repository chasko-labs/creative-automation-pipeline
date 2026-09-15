# gpu sharing protocol — 12gb card, renders + llm sessions

Single 12GB card. Residents (~6GB): vision 3.2, whisper 1.9, kokoro 0.5,
idle comfy 0.4. Free headroom moves between ~0.4GB (mid-render) and
~11.6GB (unloaded gaps). Coordination is by lock + pause file, never by
touching another owner's processes, units, or files.

## shared lock

- Valkey 127.0.0.1:16379, key `gpu_lock` (exact fc-pool key).
- Any consumer loading >4GB (glimmer, 8b, sdxl render, fc-pool burst)
  MUST hold the lock while resident and release promptly after.
- Idle-teardown stays on everywhere it exists (glimmer 300s).

## image pipeline ceiling (mine)

- Max one ComfyUI render at a time, SDXL base, 1344x768, queue :8188.
- Unload models after EVERY render; 90s grace before queueing next.
- Check the lock before queueing; wait while held; NEVER set it.
- Check `/tmp/comfy_pause` between renders; if present, wait (pauses
  within ~8 minutes, resumes on removal, nothing restarts).
- ComfyUI :8188 is the pipeline's during the campaign; scratch prefix
  `poc/comfy/` is write-once (resume skips existing keys).

## llm session ceiling (theirs)

- Embed-size loads (1-2GB): anytime, no coordination.
- Big loads (glimmer 5.4GB floor, 8b 6-7GB): take the lock first; use
  the unload gaps (they recur roughly every 8 minutes) or hold me with
  `touch /tmp/comfy_pause` for longer sessions — remove it when done.
- Never queue ComfyUI jobs while the pipeline is active; never delete
  scratch keys (resume depends on them).
- If the lock is held by a stuck owner, say so in chat instead of
  working around it.

## numbers that must keep holding

- Render transient: ~6.5GB. Unloaded idle: ~0.4GB.
- Glimmer starts at 5.4GB contiguous free; 8b wants 6-7GB.
- If all three idle residents ever get parked (owner sudo), everything
  above fits with room to spare and this protocol relaxes to lock-only.
