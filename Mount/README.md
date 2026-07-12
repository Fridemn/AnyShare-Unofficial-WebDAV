# Windows 盘符挂载教程

先按项目根目录 [README](../README.md) 和 [`.env.example`](../.env.example) 完成 `.env` 配置，并确保已经安装 `uv`。

以下命令均在仓库根目录执行。

## 安装

默认配置使用本机 HTTP WebDAV，需要允许 Windows WebClient 通过 HTTP 使用 Basic 认证：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Mount\install.ps1 -AllowHttpBasic
```

如果已为本地 WebDAV 配置受 Windows 信任的 HTTPS 证书，则不需要 `-AllowHttpBasic`：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Mount\install.ps1
```

脚本会自动请求管理员权限、创建 `.venv-windows-mount`、安装系统服务，并为当前登录用户注册盘符挂载任务。

## 验证

安装完成后，新开一个普通、非管理员 PowerShell：

```powershell
Get-Service AnyShareUnofficialWebDAVX18765
Get-ScheduledTask AnyShareUnofficialWebDAVX18765Mount
Test-NetConnection 127.0.0.1 -Port 18765
Get-Content .\Mount\mount_drive.log -Tail 20
Get-PSDrive X
Get-ChildItem X:\
```

成功日志类似：

```text
MOUNTED X: -> \\127.0.0.1@18765\DavWWWRoot
```

盘符映射属于用户登录会话。管理员 PowerShell 中看不到 `X:`，不代表普通桌面和资源管理器中的挂载失败。

## 更新配置或重新安装

修改 `.env`、更新 Cookie 或拉取新代码后，直接重新执行安装脚本，无需删除虚拟环境：

```powershell
.\Mount\install.ps1 -AllowHttpBasic
```

## 手动重挂载

在普通、非管理员 PowerShell 中执行：

```powershell
& .\.venv-windows-mount\Scripts\python.exe `
  .\Mount\mount_drive.py `
  --force `
  --log-file .\Mount\mount_drive.log
```

查看结果：

```powershell
Get-Content .\Mount\mount_drive.log -Tail 20
```

常见错误：

- `Local WebDAV authentication failed`：检查 `.env` 中的 WebDAV 用户名和密码。
- `AnyShare root listing ... HTTP 401/403`：重新登录 AnyShare，并更新 `.env` 中的完整 Cookie。
- `python3.dll PermissionError`：先执行 `Stop-Service AnyShareUnofficialWebDAVX18765 -Force`，再重新安装。

## 卸载

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Mount\uninstall.ps1
```

保留 `.venv-windows-mount`：

```powershell
.\Mount\uninstall.ps1 -KeepVenv
```
