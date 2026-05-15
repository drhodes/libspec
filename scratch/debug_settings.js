const fs = require('fs');
const path = require('path');
const os = require('os');

// Mocking the behavior of loadSettings
function getWorkspaceSettingsPath(workspaceDir) {
    return path.join(workspaceDir, '.gemini', 'settings.json');
}

const homedir = os.homedir();
const USER_SETTINGS_PATH = path.join(homedir, '.gemini', 'settings.json');
const workspaceDir = process.cwd();
const workspaceSettingsPath = getWorkspaceSettingsPath(workspaceDir);

console.log(`User settings path: ${USER_SETTINGS_PATH}`);
console.log(`Workspace settings path: ${workspaceSettingsPath}`);

try {
    const userContent = fs.readFileSync(USER_SETTINGS_PATH, 'utf-8');
    console.log("User settings content found.");
    const userSettings = JSON.parse(userContent);
    console.log("User mcpServers:", userSettings.mcpServers);
} catch (e) {
    console.log("User settings not found or invalid:", e.message);
}

try {
    const workspaceContent = fs.readFileSync(workspaceSettingsPath, 'utf-8');
    console.log("Workspace settings content found.");
    const workspaceSettings = JSON.parse(workspaceContent);
    console.log("Workspace mcpServers:", workspaceSettings.mcpServers);
} catch (e) {
    console.log("Workspace settings not found or invalid:", e.message);
}
