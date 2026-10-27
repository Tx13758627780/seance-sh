"""Shell hooks. `eval "$(seance init bash)"` and the ghost moves in."""

BASH = r'''
# --- séance: the ghost moves into this bash session ---
export SEANCE_SESSION="${SEANCE_SESSION:-bash-$$-$(date +%s)}"
__seance_armed=""
__seance_cmd=""
__seance_preexec() {
  [ -n "$COMP_LINE" ] && return
  [ -z "$__seance_armed" ] && return
  [ "$BASH_COMMAND" = "__seance_precmd" ] && return
  __seance_armed=""
  local line; line="$(HISTTIMEFORMAT= builtin history 1)"
  local num="${line%%[^ 0-9]*}"; num="${num// /}"
  if [ -n "$num" ] && [ "$num" = "$__seance_last" ]; then
    # not added to history (HISTCONTROL=ignoredups/ignorespace): fall back to the raw command
    __seance_cmd="$BASH_COMMAND"
  else
    __seance_last="$num"
    __seance_cmd="$(printf '%s' "$line" | sed -e 's/^ *[0-9]*[* ] *//')"
  fi
  __seance_start="${EPOCHREALTIME:-$(date +%s)}"
}
__seance_precmd() {
  local ec=$?
  if [ -n "$__seance_cmd" ] && [ -z "$SEANCE_HUSH" ]; then
    command seance whisper --exit "$ec" --started "$__seance_start" --cwd "$PWD" -- "$__seance_cmd"
  fi
  __seance_cmd=""
  __seance_armed=1
  return $ec
}
trap '__seance_preexec' DEBUG
case ";${PROMPT_COMMAND};" in
  *";__seance_precmd;"*) ;;
  *) PROMPT_COMMAND="__seance_precmd${PROMPT_COMMAND:+;$PROMPT_COMMAND}" ;;
esac
# --- end séance ---
'''

ZSH = r'''
# --- séance: the ghost moves into this zsh session ---
export SEANCE_SESSION="${SEANCE_SESSION:-zsh-$$-$(date +%s)}"
zmodload zsh/datetime 2>/dev/null
__seance_preexec() { __seance_cmd="$1"; __seance_start="$EPOCHREALTIME"; }
__seance_precmd() {
  local ec=$?
  if [[ -n "$__seance_cmd" && -z "$SEANCE_HUSH" ]]; then
    command seance whisper --exit "$ec" --started "$__seance_start" --cwd "$PWD" -- "$__seance_cmd"
  fi
  __seance_cmd=""
  return $ec
}
autoload -Uz add-zsh-hook
add-zsh-hook preexec __seance_preexec
add-zsh-hook precmd __seance_precmd
# --- end séance ---
'''

HOOKS = {"bash": BASH, "zsh": ZSH}
