# Demo media provenance

Video files are excluded from Git; download them again from the sources below.
`streams.json` maps each file to the mediamtx path its camera reads.

| File | Stream path | Source | Licence / allowed use |
|---|---|---|---|
| `input/first test video.mp4` | `mall-store` | Supplied in the owner's workspace; author not documented | Local engineering use; commercial clearance still to be confirmed by the owner |
| `input/stock/15007111-uhd_2560_1440_31fps.mp4` | `mall-atrium` | [Pexels: "High Angle View of a Crowded Shopping Mall", George Morina](https://www.pexels.com/video/high-angle-view-of-a-crowded-shopping-mall-15007111/) | [Pexels licence](https://www.pexels.com/license/): free commercial use, no attribution required |
| `input/stock/10868348-uhd_2560_1440_30fps.mp4` | `office-lobby` | [Pexels: "People Walking in Building", Site Engine](https://www.pexels.com/video/people-walking-in-building-10868348/) | Pexels licence |
| `input/stock/7969488-uhd_2560_1440_30fps.mp4` | `campus-lab` | [Pexels: "Students Walking in the Campus", George Pak](https://www.pexels.com/video/students-walking-in-the-campus-7969488/) | Pexels licence |

Pexels licence conditions that matter for client demos: identifiable people
must not be shown in a bad light, the demo must not imply that people or
brands in the footage endorse SmartOps, and the clips must not be resold
unaltered. Downloaded 2026-11-06 with the owner's approval.

Measured suitability (fixed camera matters for zone rules): the walkway clip
is static (0.02 px/s drift); the mall and campus clips drift slowly (about
0.5 px/s at 320 px wide). A fourth candidate (office corridor, 7147176) was
discarded because it is a moving tracking shot.

Still missing: unattended bag, blocked exit and loitering scenes. No
licensed stock footage was found; record them per
[docs/FOOTAGE_SHOT_LIST.md](../docs/FOOTAGE_SHOT_LIST.md).
