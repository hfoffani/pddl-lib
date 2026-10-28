#!/bin/sh
# Print the KEY=value lines of a .env file for the Makefile (#153), with one
# pair of surrounding quotes ('...' or "...") removed from each value, as a
# shell would. Make keeps quotes as part of a value: a quoted CORPORA_DIR
# once sent a 3 GB download into a directory named '. Other lines (comments,
# blanks) are dropped.
#
#   scripts/dotenv.sh .env
sed -n \
  -e "s/^\([A-Za-z_][A-Za-z0-9_]*\)='\(.*\)'[[:space:]]*\$/\1=\2/" -e 't p' \
  -e 's/^\([A-Za-z_][A-Za-z0-9_]*\)="\(.*\)"[[:space:]]*$/\1=\2/' -e 't p' \
  -e '/^[A-Za-z_][A-Za-z0-9_]*=/b p' \
  -e 'd' \
  -e ':p' -e 'p' \
  "$1"
