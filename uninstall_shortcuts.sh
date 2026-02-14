#!/bin/bash
# Removes Automator Quick Actions and keyboard shortcuts for translation.
# Usage: bash uninstall_shortcuts.sh

SERVICES_DIR="$HOME/Library/Services"

rm -rf "$SERVICES_DIR/Translate ES-EN.workflow"
rm -rf "$SERVICES_DIR/Translate EN-ES.workflow"

defaults write pbs NSServicesStatus \
    -dict-add '"(null) - Translate ES-EN - runWorkflowAsService"' \
    '{ "enabled_context_menu" = 0; "enabled_services_menu" = 0; }'

defaults write pbs NSServicesStatus \
    -dict-add '"(null) - Translate EN-ES - runWorkflowAsService"' \
    '{ "enabled_context_menu" = 0; "enabled_services_menu" = 0; }'

/System/Library/CoreServices/pbs -flush 2>/dev/null
killall pbs 2>/dev/null

echo "Done. Quick Actions and shortcuts removed."
