"""Shell completion commands for the Eero CLI.

Commands:
- eero completion bash: Generate bash completion
- eero completion zsh: Generate zsh completion
- eero completion fish: Generate fish completion
"""

import click

from ..context import ensure_cli_context


@click.group(name="completion")
@click.pass_context
def completion_group(ctx: click.Context) -> None:
    """Generate shell completion scripts.

    \b
    Supported shells:
      bash  - Bash completion
      zsh   - Zsh completion
      fish  - Fish completion

    \b
    Installation:
      # Bash (add to ~/.bashrc)
      eval "$(eero completion bash)"

      # Zsh (add to ~/.zshrc)
      eval "$(eero completion zsh)"

      # Fish (add to ~/.config/fish/completions/eero.fish)
      eero completion fish > ~/.config/fish/completions/eero.fish
    """
    ensure_cli_context(ctx)


@completion_group.command(name="bash")
@click.pass_context
def completion_bash(ctx: click.Context) -> None:
    """Generate bash completion script.

    \b
    Usage:
      # Add to ~/.bashrc:
      eval "$(eero completion bash)"

      # Or source from file:
      eero completion bash > /etc/bash_completion.d/eero
    """
    # Click provides shell completion via _EERO_COMPLETE
    script = """
_eero_completion() {
    local IFS=$'\\n'
    COMPREPLY=( $( env COMP_WORDS="${COMP_WORDS[*]}" \\
                   COMP_CWORD=$COMP_CWORD \\
                   _EERO_COMPLETE=complete_bash $1 ) )
    return 0
}

complete -F _eero_completion -o default eero
"""
    click.echo(script)


@completion_group.command(name="zsh")
@click.pass_context
def completion_zsh(ctx: click.Context) -> None:
    """Generate zsh completion script.

    \b
    Usage:
      # Add to ~/.zshrc:
      eval "$(eero completion zsh)"

      # Or add to fpath:
      eero completion zsh > ~/.zsh/completions/_eero
    """
    script = """
#compdef eero

_eero() {
    local -a completions
    local -a completions_with_descriptions
    local -a response
    (( ! $+commands[eero] )) && return 1

    response=("${(@f)$(env COMP_WORDS="${words[*]}" COMP_CWORD=$((CURRENT-1)) _EERO_COMPLETE=complete_zsh eero)}")

    for key descr in ${(kv)response}; do
        if [[ "$descr" == "_" ]]; then
            completions+=("$key")
        else
            completions_with_descriptions+=("$key":"$descr")
        fi
    done

    if [ -n "$completions_with_descriptions" ]; then
        _describe -V unsorted completions_with_descriptions -U
    fi

    if [ -n "$completions" ]; then
        compadd -U -V unsorted -a completions
    fi
}

compdef _eero eero
"""
    click.echo(script)


@completion_group.command(name="fish")
@click.pass_context
def completion_fish(ctx: click.Context) -> None:
    """Generate fish completion script.

    \b
    Usage:
      # Save to fish completions directory:
      eero completion fish > ~/.config/fish/completions/eero.fish
    """
    script = """
function _eero_completion
    set -l response (env _EERO_COMPLETE=complete_fish COMP_WORDS=(commandline -cp) COMP_CWORD=(commandline -t) eero)

    for completion in $response
        set -l metadata (string split "," -- $completion)

        if [ $metadata[1] = "plain" ]
            echo $metadata[2]
        else if [ $metadata[1] = "dir" ]
            __fish_complete_directories $metadata[2]
        else if [ $metadata[1] = "file" ]
            __fish_complete_path $metadata[2]
        end
    end
end

complete --no-files --command eero --arguments "(_eero_completion)"
"""
    click.echo(script)
