#!/bin/bash
# Creates Automator Quick Actions for translation shortcuts.
# Usage: bash install_shortcuts.sh

SERVICES_DIR="$HOME/Library/Services"
PORT=8785

create_workflow() {
    local name="$1" src="$2" tgt="$3" title="$4"
    local dir="$SERVICES_DIR/$name.workflow/Contents"

    mkdir -p "$dir"

    local script
    script=$(cat <<'SCRIPT'
# Absolute paths
PROJECT_DIR="PROJECT_DIR_PLACEHOLDER"

# Check/start server
"$PROJECT_DIR/check_server.sh"

# Get selected text and encode as base64 (URL-safe)
TEXT=$(cat)
ENCODED=$(python3 -c "import sys, base64; print(base64.urlsafe_b64encode(sys.stdin.read().encode()).decode())" <<< "$TEXT")

# Open browser with encoded text in URL
open "http://127.0.0.1:8785/?src=SRC_LANG_PLACEHOLDER&tgt=TGT_LANG_PLACEHOLDER&text=$ENCODED"
SCRIPT
)
    # Replace placeholders with actual values
    script="${script//PROJECT_DIR_PLACEHOLDER/$(pwd)}"
    script="${script//SRC_LANG_PLACEHOLDER/${src}}"
    script="${script//TGT_LANG_PLACEHOLDER/${tgt}}"

    cat > "$dir/document.wflow" <<'PLIST_HEAD'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>AMApplicationBuild</key>
	<string>523</string>
	<key>AMApplicationVersion</key>
	<string>2.10</string>
	<key>AMDocumentVersion</key>
	<string>2</string>
	<key>actions</key>
	<array>
		<dict>
			<key>action</key>
			<dict>
				<key>AMAccepts</key>
				<dict>
					<key>Container</key>
					<string>List</string>
					<key>Optional</key>
					<true/>
					<key>Types</key>
					<array>
						<string>com.apple.cocoa.string</string>
					</array>
				</dict>
				<key>AMActionVersion</key>
				<string>2.0.3</string>
				<key>AMApplication</key>
				<array>
					<string>Automator</string>
				</array>
				<key>AMCategory</key>
				<string>AMCategoryUtilities</string>
				<key>AMIconName</key>
				<string>Run Shell Script</string>
				<key>AMParameterProperties</key>
				<dict>
					<key>COMMAND_STRING</key>
					<dict/>
					<key>CheckedForUserDefaultShell</key>
					<dict/>
					<key>inputMethod</key>
					<dict/>
					<key>shell</key>
					<dict/>
					<key>source</key>
					<dict/>
				</dict>
				<key>AMProvides</key>
				<dict>
					<key>Container</key>
					<string>List</string>
					<key>Types</key>
					<array>
						<string>com.apple.cocoa.string</string>
					</array>
				</dict>
				<key>ActionBundlePath</key>
				<string>/System/Library/Automator/Run Shell Script.action</string>
				<key>ActionName</key>
				<string>Run Shell Script</string>
				<key>ActionParameters</key>
				<dict>
					<key>COMMAND_STRING</key>
PLIST_HEAD

    # Write the script content (XML-escaped) and close the plist
    echo "					<string>$(echo "$script" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g')</string>" >> "$dir/document.wflow"

    cat >> "$dir/document.wflow" <<'PLIST_TAIL'
					<key>CheckedForUserDefaultShell</key>
					<true/>
					<key>inputMethod</key>
					<integer>0</integer>
					<key>shell</key>
					<string>/bin/bash</string>
					<key>source</key>
					<string></string>
				</dict>
				<key>BundleIdentifier</key>
				<string>com.apple.RunShellScript</string>
				<key>CFBundleVersion</key>
				<string>2.0.3</string>
				<key>CanShowSelectedItemsWhenRun</key>
				<false/>
				<key>CanShowWhenRun</key>
				<true/>
				<key>Category</key>
				<array>
					<string>AMCategoryUtilities</string>
				</array>
				<key>Class Name</key>
				<string>RunShellScriptAction</string>
				<key>InputUUID</key>
				<string>A9AAE02E-BBBB-4444-AAAA-111111111111</string>
				<key>Keywords</key>
				<array>
					<string>Shell</string>
					<string>Script</string>
					<string>Command</string>
					<string>Run</string>
					<string>Unix</string>
				</array>
				<key>OutputUUID</key>
				<string>B8BBF13F-CCCC-5555-BBBB-222222222222</string>
				<key>UUID</key>
				<string>C7CCD24D-DDDD-6666-CCCC-333333333333</string>
				<key>UnlocalizedApplications</key>
				<array>
					<string>Automator</string>
				</array>
			</dict>
		</dict>
	</array>
	<key>connectors</key>
	<dict/>
	<key>workflowMetaData</key>
	<dict>
		<key>serviceInputTypeIdentifier</key>
		<string>com.apple.Automator.text</string>
		<key>serviceOutputTypeIdentifier</key>
		<string>com.apple.Automator.nothing</string>
		<key>serviceProcessesInput</key>
		<integer>0</integer>
		<key>workflowTypeIdentifier</key>
		<string>com.apple.Automator.servicesMenu</string>
	</dict>
</dict>
</plist>
PLIST_TAIL

    cat > "$dir/Info.plist" <<'INFO'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>NSServices</key>
	<array>
		<dict>
			<key>NSMenuItem</key>
			<dict>
				<key>default</key>
				<string>WORKFLOW_NAME</string>
			</dict>
			<key>NSMessage</key>
			<string>runWorkflowAsService</string>
			<key>NSSendTypes</key>
			<array>
				<string>NSStringPboardType</string>
			</array>
		</dict>
	</array>
</dict>
</plist>
INFO
    sed -i '' "s/WORKFLOW_NAME/$name/" "$dir/Info.plist"

    echo "Created: $SERVICES_DIR/$name.workflow"
}

create_workflow "Translate ES-EN" "es" "en" "ES → EN"
create_workflow "Translate EN-ES" "en" "es" "EN → ES"

# Assign keyboard shortcuts: @=CMD, $=SHIFT
defaults write pbs NSServicesStatus \
    -dict-add '"(null) - Translate ES-EN - runWorkflowAsService"' \
    '{ "enabled_context_menu" = 1; "enabled_services_menu" = 1; "key_equivalent" = "@$e"; }'

defaults write pbs NSServicesStatus \
    -dict-add '"(null) - Translate EN-ES - runWorkflowAsService"' \
    '{ "enabled_context_menu" = 1; "enabled_services_menu" = 1; "key_equivalent" = "@$i"; }'

# Refresh the services menu
/System/Library/CoreServices/pbs -flush 2>/dev/null
killall pbs 2>/dev/null

echo ""
echo "Done. Shortcuts installed:"
echo "  CMD+SHIFT+E -> Translate ES-EN"
echo "  CMD+SHIFT+I -> Translate EN-ES"
