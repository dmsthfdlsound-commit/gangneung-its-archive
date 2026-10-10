"""강릉시 교통정보 한 장 찍어 두기 → data/YYYY/MM/DD/HHMM.json (한국 시각)

자료: 강릉 3D 지도의 서버 함수(https://gangneung-map.vercel.app/api/gn-its).
      그 함수가 공공데이터포털 '강원특별자치도 강릉시_교통정보 조회서비스'를 불러 5분 동안 저장해 둔다.
      그래서 이 저장소에는 인증키가 필요 없다.
남기는 것: 주차장 차 수, 스마트교차로 서비스수준·지체, 회전교차로, 스마트횡단보도, 돌발.
주차장 이름·주소·좌표처럼 잘 안 바뀌는 것은 data/parking_info.json 에 따로 한 번만.
같은 기준 시각을 두 번 저장하지 않는다 (data/latest.txt).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

API = "https://gangneung-map.vercel.app/api/gn-its"
ROOT = Path(__file__).resolve().parents[1] / "data"


def fetch() -> dict:
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(API, headers={"User-Agent": "gangneung-its-archive"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001 - 잠깐 뒤 다시
            if "CERTIFICATE" in str(e):  # 맥의 파이썬은 인증서 문제로 실패할 때가 있어 curl 로
                import subprocess
                return json.loads(subprocess.run(["curl", "-sS", "-m", "60", API], capture_output=True, text=True, check=True).stdout)
            last = e
            time.sleep(10)
    raise RuntimeError(f"받기 실패: {last}")


def main() -> int:
    d = fetch()
    updated = d.get("updated")  # "2026-10-10 14:09" (한국 시각)
    if not updated or not d.get("parking"):
        print("자료가 비어 있어 건너뜀", d.get("errors"), file=sys.stderr)
        return 0
    latest = ROOT / "latest.txt"
    if latest.exists() and latest.read_text().strip() == updated:
        print(f"{updated} 은 이미 저장함")
        return 0

    info_path = ROOT / "parking_info.json"
    info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
    for p in d["parking"]:
        info[p["id"]] = {k: p.get(k) for k in ("name", "addr", "lon", "lat", "type", "open", "total")}
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

    snap = {
        "updated": updated,
        # 주차장: [아이디, 전체 면수, 주차한 차 수]  (차 수 0 은 실시간 자료가 없는 곳이 많음)
        "parking": [[p["id"], p.get("total"), p.get("used")] for p in d["parking"]],
        # 스마트교차로: [이름, 서비스수준(가장 나쁜 방향), 최대 지체(초), 교통량 합, 집계 시각]
        "smart": [[s["name"], s.get("los"), s.get("delay"), s.get("volume"), s.get("at")] for s in d.get("smart", [])],
        # 회전교차로: [이름, 교통량, 평균 속도, 통행시간, 집계 시각]
        "rond": [[r["name"], r.get("volume"), r.get("speed"), r.get("time"), r.get("at")] for r in d.get("rond", [])],
        # 스마트횡단보도(오늘 누적): [이름, 건넌 사람, 무단횡단]
        "crosswalk": [[w["name"], w.get("across"), w.get("jaywalking")] for w in d.get("crosswalk", [])],
        # 돌발: [이름, 단계, 감지 시각]
        "incidents": [[i.get("name"), i.get("level"), i.get("at")] for i in d.get("incidents", [])],
        "errors": d.get("errors", []),
    }
    day, hm = updated.split(" ")
    y, m, dd = day.split("-")
    out = ROOT / y / m / dd / f"{hm.replace(':', '')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    latest.write_text(updated + "\n")
    print(f"저장: {out.relative_to(ROOT.parent)} ({out.stat().st_size:,} 바이트)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
