#!/usr/bin/env bash
set -euo pipefail

# Safe per-mapping backup + update runner
# Usage:
#   export LIBPQ_DATABASE_URL="postgresql://..."
#   bash scripts/check_services.sh   # recommended
#   bash scripts/apply_subsidy_mappings.sh

OUTDIR="$(pwd)/outgoing_patches"
mkdir -p "$OUTDIR"

if [[ -z "${LIBPQ_DATABASE_URL:-}" ]]; then
  echo "ERROR: LIBPQ_DATABASE_URL not set. Export it and re-run."
  exit 1
fi

PAIR_OUT="/tmp/subsidy_migration_pairs.txt"
: > "$PAIR_OUT"

echo "Starting per-mapping backup + update run at $(date -u)"

mapfile -t LINES <<'MAP'
더 뉴 아이오닉6 2wd 롱레인지 18인치||더 뉴 아이오닉6 롱레인지 2WD 18인치
더 뉴 아이오닉6 2wd 스탠다드 18인치||더 뉴 아이오닉6 스탠다드 2WD 18인치
더 뉴 아이오닉6 2wd 롱레인지 20인치||더 뉴 아이오닉6 롱레인지 2WD 20인치
더 뉴 아이오닉6 2wd 롱레인지 n라인 20인치||더 뉴 아이오닉6 롱레인지 N라인 2WD 20인치
더 뉴 아이오닉6 awd 롱레인지 18인치||더 뉴 아이오닉6 롱레인지 AWD 18인치
더 뉴 아이오닉6 awd 롱레인지 20인치||더 뉴 아이오닉6 롱레인지 AWD 20인치
더 뉴 아이오닉6 awd 롱레인지 n라인 20인치||더 뉴 아이오닉6 롱레인지 N라인 AWD 20인치

코나 일렉트릭 2WD 롱레인지 17인치||코나 일렉트릭 롱레인지 2WD 17인치
코나 일렉트릭 2WD 스탠다드 17인치||코나 일렉트릭 스탠다드 2WD 17인치
코나 일렉트릭 2WD 롱레인지 17인치(빌트인 캠)||코나 일렉트릭 롱레인지 2WD 17인치(빌트인 캠)
코나 일렉트릭 2WD 롱레인지 19인치(빌트인 캠)||코나 일렉트릭 롱레인지 2WD 19인치(빌트인 캠)

더뉴아이오닉5 2WD 롱레인지 19인치||더 뉴 아이오닉5 롱레인지 2WD 19인치
더뉴아이오닉5 2WD 스탠다드 19인치||더 뉴 아이오닉5 스탠다드 2WD 19인치
더뉴아이오닉5 2WD 롱레인지 19인치 빌트인 캠 미적용||더 뉴 아이오닉5 롱레인지 2WD 19인치(빌트인 캠 미적용)
더뉴아이오닉5 2WD 롱레인지 20인치||더 뉴 아이오닉5 롱레인지 2WD 20인치
더뉴아이오닉5 2WD 롱레인지 N라인 20인치||더 뉴 아이오닉5 N라인 롱레인지 2WD 20인치
더뉴아이오닉5 AWD 롱레인지 19인치||더 뉴 아이오닉5 롱레인지 AWD 19인치
더뉴아이오닉5 AWD 롱레인지 20인치||더 뉴 아이오닉5 롱레인지 AWD 20인치
더뉴아이오닉5 AWD 롱레인지 N라인 20인치||더 뉴 아이오닉5 롱레인지 N라인 AWD 20인치
아이오닉5 N||아이오닉5 N라인

더뉴EV6 스탠다드||더 뉴 EV6 스탠다드
더뉴EV6 롱레인지 2WD 19인치||더 뉴 EV6 롱레인지 2WD 19인치
더뉴EV6 롱레인지 2WD 20인치||더 뉴 EV6 롱레인지 2WD 20인치
더뉴EV6 롱레인지 4WD 19인치||더 뉴 EV6 롱레인지 4WD 19인치
더뉴EV6 롱레인지 4WD 20인치||더 뉴 EV6 롱레인지 4WD 20인치
더뉴EV6 GT||더 뉴 EV6 GT

scenic||SCENIC

Polestar 4 Long Range Dual Motor 20인치||Polestar 4 롱레인지 Dual Motor 20인치
Polestar 4 Long Range Dual Motor 22인치 performance||Polestar 4 롱레인지 Dual Motor 22인치 performance
Polestar 4 Long Range Single Motor 20인치||Polestar 4 롱레인지 Single Motor 20인치

볼보 EX 30cc Twin||볼보 EX30 Ultra
볼보 EX30 Single Motor ER||볼보 EX30 Core

BYD SEAL Dynamic awd||BYD SEAL Dynamic AWD
MAP

i=0
for raw in "${LINES[@]}"; do
  [[ -z "$raw" ]] && continue
  i=$((i+1))
  old=${raw%%||*}
  new=${raw#*||}
  old=$(echo "$old" | sed 's/^\s*//;s/\s*$//')
  new=$(echo "$new" | sed 's/^\s*//;s/\s*$//')
  old_esc=$(printf "%s" "$old" | sed "s/'/''/g")
  new_esc=$(printf "%s" "$new" | sed "s/'/''/g")

  echo "[${i}] Processing mapping: '${old}' -> '${new}'"
  cnt_before=$(psql "$LIBPQ_DATABASE_URL" -t -A -c "SELECT COUNT(*) FROM subsidies WHERE model_name = '${old_esc}';") || cnt_before=0
  echo "[${i}] rows_before=${cnt_before}"

  ts=$(date +%Y%m%d_%H%M%S)
  backup_file="$OUTDIR/subsidy_backup_${i}_${ts}.csv"
  if [[ "$cnt_before" -gt 0 ]]; then
    echo "[${i}] Creating backup CSV -> ${backup_file}"
    psql "$LIBPQ_DATABASE_URL" -c "COPY (SELECT * FROM subsidies WHERE model_name = '${old_esc}') TO STDOUT WITH CSV HEADER" > "$backup_file"
  else
    echo "[${i}] No rows found for '${old}', creating empty backup file"
    printf "" > "$backup_file"
  fi

  echo "[${i}] Running UPDATE"
  psql "$LIBPQ_DATABASE_URL" -c "BEGIN; UPDATE subsidies SET model_name = '${new_esc}' WHERE model_name = '${old_esc}'; COMMIT;"

  cnt_after_old=$(psql "$LIBPQ_DATABASE_URL" -t -A -c "SELECT COUNT(*) FROM subsidies WHERE model_name = '${old_esc}';") || cnt_after_old=0
  cnt_after_new=$(psql "$LIBPQ_DATABASE_URL" -t -A -c "SELECT COUNT(*) FROM subsidies WHERE model_name = '${new_esc}';") || cnt_after_new=0
  echo "[${i}] Verification: remaining_old=${cnt_after_old}, total_new=${cnt_after_new}"

  printf "%s||%s\n" "$old_esc" "$new_esc" >> "$PAIR_OUT"
done

echo "Finished per-mapping run. Backups in: $OUTDIR" 
echo "Migration pairs written to: $PAIR_OUT"

exit 0
