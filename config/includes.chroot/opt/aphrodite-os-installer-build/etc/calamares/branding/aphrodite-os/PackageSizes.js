WorkerScript.onMessage = function(request) {
    const seen = {}
    let download = 0, installed = 0, unknown = 0, runtimes = false
    for (const id of Object.keys(request.apps)) {
        const method = request.apps[id]
        if (method === "flatpak") runtimes = true
        const info = request.metadata[id] && request.metadata[id][method]
        if (!info || !info.packages) {
            unknown++
            continue
        }
        for (const pkg of Object.keys(info.packages)) {
            if (seen[pkg]) continue
            seen[pkg] = true
            download += info.packages[pkg][0]
            installed += info.packages[pkg][1]
        }
    }
    WorkerScript.sendMessage({revision: request.revision, download, installed, unknown, runtimes})
}
