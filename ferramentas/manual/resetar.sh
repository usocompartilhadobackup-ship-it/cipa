#!/bin/sh
# Recria o banco LOCAL usado só para os prints do manual, com dados fictícios.
# Nunca aponte para o Supabase: este script apaga o banco inteiro.
set -e
DIR=$(cd "$(dirname "$0")" && pwd)
PGHOST=${PGHOST:-localhost}
case "$PGHOST" in localhost|127.0.0.1|::1) ;; *) echo "Recusado: PGHOST precisa ser local ($PGHOST)"; exit 1;; esac
BANCO=${BANCO_MANUAL:-quiz_manual}
PSQL="psql -h $PGHOST -p ${PGPORT:-5432} -U ${PGUSER:-postgres} -q -v ON_ERROR_STOP=1"
$PSQL -d postgres -c "drop database if exists $BANCO with (force)"
$PSQL -d postgres -c "create database $BANCO"
$PSQL -d $BANCO -f "$DIR/../../supabase/01-banco.sql" > /dev/null
$PSQL -d $BANCO -f "$DIR/dados-exemplo.sql" > /dev/null
echo "Banco $BANCO recriado com dados fictícios"
