# Windows 系统服务与盘符挂载

该目录提供两个协作组件：

1. `service.py` 作为 LocalSystem Windows 服务，读取项目根目录 `.env`，直接构造 `AuthenticatedClient`、`AnyShareRepository` 和 WsgiDAV 服务。
2. `mount_drive.py` 在用户登录会话中通过 Windows WebClient Redirector 映射盘符。

Windows 的盘符映射属于登录会话。系统服务创建的盘符不会出现在普通用户的资源管理器中，因此安装器使用“系统服务 + 用户登录计划任务”，而不是在服务中运行 `net use`。

安装器使用 `uv` 在项目根目录创建专用 `.venv-windows-mount`，并通过 `uv sync --locked --extra windows-mount` 安装锁定依赖。服务和计划任务只使用该环境的 Python，不读取或修改 Windows 全局 Python 包。

## 配置

先填写项目根目录 `.env`。除网关已有字段外，支持：

```dotenv
ANYSHARE_MOUNT_DRIVE=X:
ANYSHARE_MOUNT_URL=
ANYSHARE_MOUNT_TLS_VERIFY=true
ANYSHARE_MOUNT_WAIT_SECONDS=60
```

- `ANYSHARE_MOUNT_URL` 留空时，从 `ANYSHARE_DAV_HOST/PORT` 和证书配置推导。
- Windows WebClient 使用 Basic 认证时，正式使用建议配置受 Windows 信任的 HTTPS 证书。
- `.env` 包含云端 Cookie 和本地挂载密码，安装器会限制其 ACL。

## 安装

先安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)，然后执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Mount\install.ps1
```

脚本检测到当前终端不是管理员时会自动弹出 UAC 提权窗口，并把原登录用户保留为盘符挂载用户。

如果仅在本机使用 HTTP 且暂时没有受信任证书，可显式启用 Windows WebClient 的 HTTP Basic（这是系统级弱化设置，不建议用于会访问不受信任 WebDAV 站点的电脑）：

```powershell
.\Mount\install.ps1 -AllowHttpBasic
```

指定 uv、隔离环境使用的 Python 版本、配置文件或实际挂载用户：

```powershell
.\Mount\install.ps1 `
  -Uv 'C:\Tools\uv.exe' `
  -PythonVersion '3.11' `
  -VenvDir 'C:\ProgramData\AnyShareWebDAV\venv' `
  -EnvFile 'C:\ProgramData\AnyShareWebDAV\.env' `
  -MountUser 'DOMAIN\alice'
```

安装器会：

- 使用 `uv.lock` 创建并同步隔离的 `windows-mount` 环境；
- 将 `pythonservice.exe` 和所需 Python/pywin32 DLL 布置在隔离环境 `Scripts` 目录；
- 注册并启动 `AnyShareUnofficialWebDAVX18765` 服务；
- 启动 Windows `WebClient` 服务；
- 注册当前用户登录时执行的盘符挂载任务；
- 使用带认证的 `PROPFIND` 检查 WebDAV 内容，并实际读取盘符后才报告成功；
- 将每次登录挂载的结果追加到 `Mount\mount_drive.log`；
- 限制 `.env` 为 SYSTEM、管理员和挂载用户可读。

## 手动操作

```powershell
# 在当前用户会话挂载
.\.venv-windows-mount\Scripts\python.exe .\Mount\mount_drive.py --force --log-file .\Mount\mount_drive.log

# 卸载
.\.venv-windows-mount\Scripts\python.exe .\Mount\mount_drive.py --unmount --force

# 服务调试（前台运行）
.\.venv-windows-mount\Scripts\python.exe .\Mount\service.py debug

# 查看最后的挂载结果
Get-Content .\Mount\mount_drive.log -Tail 20
```

## 卸载

```powershell
.\Mount\uninstall.ps1
```

默认卸载会同时删除 `.venv-windows-mount`。需要保留依赖环境时使用 `-KeepVenv`。

Windows Server 可能需要先安装 WebDAV Redirector/Desktop Experience。若使用 HTTPS，证书的主机名必须与挂载 URL 匹配并受 Windows 信任。
