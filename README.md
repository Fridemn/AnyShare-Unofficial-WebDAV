AnyShare-Unofficial
==========
AiShu AnyShare Cloud Drive Unofficial API Client Library  
爱数 AnyShare 云盘非官方 API 库

## 简介 <sub>Intro</sub>

此项目是爱数 Anyshare 云盘的非官方 Python API 库，支持对 Anyshare v7.0（2025 年构建版）云盘服务进行 API 操作。

> PyPI 项目主页：https://pypi.org/project/AnyShare-Unofficial

> PyPI 上发布的最新版本：![PyPI Release](https://img.shields.io/pypi/v/AnyShare-Unofficial?label=)

### 实现的功能

- `AnonymousClient`：匿名分享链接访问，支持的功能包括：
  - 浏览分享链接中的文件和文件夹；
  - 下载和上传文件（如果该分享链接开启了对应权限）。

- `AuthenticatedClient`：基于已登录用户的会话 Cookie 认证访问，支持的功能包括：
  - 获取用户信息和存储配额；
  - 浏览文档库和文件夹的内容；
  - 上传、下载、删除、移动和重命名文件；
  - 联系人和部门信息查询；
  - 共享管理查询。

## 使用方法 <sub>Usage</sub>

### 安装

需要 **Python** 3.9 或更高版本。

需要安装 `httpx>=0.28.1`和 `pydantic>=2.13.4` 库。

随后通过下面的命令安装本库：

```bash
pip install anyshare-unofficial
# 或
poetry add anyshare-unofficial
```

### 示例：匿名访问云盘

借助 `AnonymousClient` 能力，无需登录，只要获得了**分享链接**即可浏览、下载文件。如果分享链接开放了上传权限，也可上传文件。

```python
from anyshare_unofficial import AnonymousClient, OnDup

# 创建匿名客户端实例
client = AnonymousClient(
    "https://example.com/link/ABC123...",  # 这里填分享链接
    base_url="https://example.com",  # 这里填云盘主URL
)

# 列出分享链接中的条目
entries = client.list_entries()
# 更常用的做法
entry = client.get_first_entry()

# 递归浏览文件夹
contents = client.browse_folder(entry.id)
for f in contents.files:
    print(f"{f.name} ({f.size / 1024:.1f} KB)")

# 下载文件
file = contents.files[0]
auth, result = client.get_download_url(contents.files[0])
print(f"name={result.name}, link={auth.url}")
# 更简单的做法
client.download_file(file, "/local/path/")

# 覆盖上传（需要分享链接开放上传权限）
client.upload_file("/local/file.pdf", entry.id, ondup=OnDup.OVERWRITE)
```

### 示例：认证访问云盘

借助 `AuthenticatedClient` 能力，传入已获取的**会话 Cookie** 字符串，即可使用全部的 API。

```python
from anyshare_unofficial import AuthenticatedClient, OnDup

# 创建认证客户端实例
client = AuthenticatedClient(
    "Authorization=xxx; JSESSIONID=xxx; ...",  # 这里填 Cookie
    base_url="https://example.com",
)

# 获取用户信息和配额
user = client.get_current_user()
print(f"User: {user.name} ({user.account})")
quota = client.get_quota()
print(f"Quota: {quota.used / 1024 ** 3:.1f}/{quota.allocated / 1024 ** 3:.1f}GB")

# 浏览文档库
doc_libs = client.list_doc_libs()
for lib in doc_libs:
    print(f"Doc lib: {lib.name} ({lib.type})")

# 浏览文件夹
content = client.browse_folder(doc_libs[0].id)
for d in content.dirs:
    print(f"Dir: {d.name}")
for f in content.files:
    print(f"File: {f.name} ({f.size / 1024:.1f} KB)")

# 删除和移动文件
# GNS 路径可以通过 file.id 获取
client.delete_file("gns://xxx/file")
client.move_file("gns://xxx/file", "gns://xxx/dest", ondup=OnDup.OVERWRITE)

# 创建目录
client.create_directory("gns://xxx/parent", "NewFolder", ondup=OnDup.RENAME)

# 下载文件
auth, result = client.get_download_url("gns://xxx/file", savename="file.pdf")
# 或者更简单的做法
client.download_file("gns://xxx/file", "/downloads/", savename="file.pdf")

# 联系人与部门
groups = client.get_contact_groups()
depts = client.get_department_roots()

# 共享管理
shares = client.list_shares_with_anyone()

# 关闭连接
client.close()
```

## WebDAV 网关（实验性）

安装 WebDAV 可选依赖：

```bash
pip install "AnyShare-Unofficial[webdav]"
# 在源码仓库中开发
poetry install -E webdav
```

通过命令行参数和系统环境变量提供配置：

```bash
export ANYSHARE_AUTH_COOKIE='Authorization=Bearer ...; JSESSIONID=...'
anyshare-webdav \
  --base-url https://anyshare.example.com \
  --username anyshare-dav \
  --password 'change-this-password'
```

在 Poetry 环境中使用 `poetry run anyshare-webdav`。除 `ANYSHARE_AUTH_COOKIE` 外，CLI 参数均可用同名 `ANYSHARE_DAV_*` 环境变量配置；命令行参数优先。不要把真实 Cookie 或密码提交到仓库。

服务根目录会把当前账号可访问的文档库显示为一级目录。支持目录浏览、Range 下载、上传、建目录、删除、移动、重命名以及 WebDAV 锁。默认只监听本机；如果需要从其他设备访问，请在前方配置可信 HTTPS 反向代理，或通过 `--certfile` 和 `--keyfile` 启用 HTTPS。不要通过明文 HTTP 暴露 Basic 认证或 AnyShare Cookie。

Windows 可使用以下方式映射盘符：

```powershell
net use X: https://dav.example.com/ /user:anyshare-x *
```

Windows WebClient 通常要求 Basic 认证使用受信任的 HTTPS 连接，因此证书需要被 Windows 信任。本机明文 HTTP 仅适合已明确允许该认证方式的测试客户端。

需要注册为 Windows 系统服务并在用户登录后自动映射盘符时，使用 [`scripts/`](scripts/README.md) 中的安装器：

```powershell
.\scripts\install.ps1
```

当前限制：`COPY` 尚未实现；文件重命名采用下载、按新名称上传、删除旧文件的兼容流程；跨目录并同时重命名文件夹尚不支持。锁和自定义属性由网关进程内存保存，服务重启后失效。

## API 概览 <sub>API Overview</sub>

### 1. 基类（BaseClient）

客户端均继承自此基类，提供 HTTP 会话管理和错误处理。

### 2. 匿名客户端（AnonymousClient）

| 方法               | 端点                                                                            | 说明                          |
| ------------------ | ------------------------------------------------------------------------------- | ----------------------------- |
| `list_entries`     | GET `/api/efast/v1/entry-item`                                                  | 列出分享链接中的顶层条目      |
| `browse_folder`    | GET `/api/efast/v1/folders/{gns_path}/sub_objects`                              | 浏览指定 GNS 路径的文件夹内容 |
| `get_download_url` | POST `/api/efast/v1/file/osdownload`                                            | 获取文件预签名下载 URL        |
| `download_file`    | (组合)                                                                          | 获取下载 URL 后流式下载到本地 |
| `upload_file`      | POST `/api/efast/v1/file/osbeginupload` → S3 → `/api/efast/v1/file/osendupload` | 三步上传                      |
| `set_cookie`       | —                                                                               | 设置 Cookie 并更新认证头      |
| `refresh_token`    | GET `/anyshare/oauth2/login/refreshToken`                                       | 刷新 OAuth2 令牌              |

### 3. 认证客户端（AuthenticatedClient）

#### 用户

| 方法                  | 端点                                      | 说明                         |
| --------------------- | ----------------------------------------- | ---------------------------- |
| `get_config`          | GET `/api/eacp/v1/auth1/configs`          | 获取配置                     |
| `get_login_config`    | GET `/api/eacp/v1/auth1/login-configs`    | 获取登录配置（含第三方 SSO） |
| `get_current_user`    | POST `/api/eacp/v1/user/get`              | 获取当前用户信息             |
| `get_user_basic_info` | POST `/api/eacp/v1/user/getbasicinfo`     | 获取指定用户基本信息         |
| `refresh_token`       | GET `/anyshare/oauth2/login/refreshToken` | 刷新 OAuth2 令牌             |

> 注意：`get_user_basic_info()` 的 `directdepinfos` 可能只包含部门路径 `deppath`，不同于 `get_current_user()` 返回的标准部门对象。

#### 文档库

| 方法                       | 端点                                          | 说明               |
| -------------------------- | --------------------------------------------- | ------------------ |
| `list_doc_libs`            | GET `/api/efast/v1/entry-doc-lib`             | 列出可访问的文档库 |
| `list_classified_doc_libs` | GET `/api/efast/v1/classified-entry-doc-libs` | 列出分类文档库     |

#### 文件浏览

| 方法                | 端点                                               | 说明                                       |
| ------------------- | -------------------------------------------------- | ------------------------------------------ |
| `browse_folder`     | GET `/api/efast/v1/folders/{gns_path}/sub_objects` | 浏览文件夹内容（支持排序、分页、模式过滤） |
| `get_file_metadata` | POST `/api/efast/v1/file/metadata`                 | 获取文件元数据                             |
| `get_item_detail`   | GET `/api/efast/v2/items/{object_id}/all`          | 获取条目详细信息（含路径、权限）           |

#### 文件操作

| 方法               | 端点                                     | 说明                     |
| ------------------ | ---------------------------------------- | ------------------------ |
| `get_download_url` | POST `/api/efast/v1/file/osdownload`     | 获取预签名下载 URL       |
| `download_file`    | (组合 get_download_url + 流式 HTTP GET)  | 下载文件到本地           |
| `delete_file`      | POST `/api/efast/v1/file/delete`         | 删除文件                 |
| `move_file`        | POST `/api/efast/v1/file/move`           | 移动文件到目标目录       |
| `get_suggest_name` | POST `/api/efast/v1/file/getsuggestname` | 获取建议文件名（防冲突） |

#### 目录操作

| 方法                   | 端点                                    | 说明                     |
| ---------------------- | --------------------------------------- | ------------------------ |
| `create_directory`     | POST `/api/efast/v1/dir/create`         | 创建文件夹               |
| `rename_directory`     | POST `/api/efast/v1/dir/rename`         | 重命名文件夹             |
| `get_suggest_dir_name` | POST `/api/efast/v1/dir/getsuggestname` | 获取建议目录名（防冲突） |

#### 上传

| 方法               | 端点                                 | 说明       |
| ------------------ | ------------------------------------ | ---------- |
| `upload_file_s3`   | POST begin → S3 POST → end           | 文件上传   |
| `predupload_check` | POST `/api/efast/v1/file/predupload` | 预上传检查 |

#### 权限

| 方法               | 端点                                        | 说明                 |
| ------------------ | ------------------------------------------- | -------------------- |
| `get_quota`        | GET `/api/efast/v1/quota/user`              | 获取存储配额         |
| `check_permission` | POST `/api/eacp/v1/perm1/check`             | 检查对指定对象的权限 |
| `get_share_config` | POST `/api/eacp/v1/perm1/getsharedocconfig` | 获取共享策略配置     |
| `get_lock_info`    | POST `/api/eacp/v1/autolock/getlockinfo`    | 获取文件锁定状态     |

#### 联系人

| 方法                   | 端点                                       | 说明               |
| ---------------------- | ------------------------------------------ | ------------------ |
| `get_contact_groups`   | POST `/api/eacp/v1/contactor/getgroups`    | 获取联系人分组列表 |
| `get_contact_persons`  | POST `/api/eacp/v1/contactor/getpersons`   | 获取分组内联系人   |
| `get_department_roots` | POST `/api/eacp/v1/department/getroots`    | 获取根级部门列表   |
| `get_sub_departments`  | POST `/api/eacp/v1/department/getsubdeps`  | 获取子部门         |
| `get_department_users` | POST `/api/eacp/v1/department/getsubusers` | 获取部门内用户     |

#### 共享管理

| 方法                      | 端点                                            | 说明                     |
| ------------------------- | ----------------------------------------------- | ------------------------ |
| `list_shares_with_users`  | GET `/api/doc-share/v1/docs-shared-with-users`  | 列出分享给指定用户的文档 |
| `list_shares_with_anyone` | GET `/api/doc-share/v1/docs-shared-with-anyone` | 列出分享给所有人的文档   |
| `list_blocked_doc_libs`   | GET `/api/doc-share/v1/blocked-doc-lib`         | 列出已屏蔽的文档库       |

#### 其他

| 方法                | 端点                                | 说明                         |
| ------------------- | ----------------------------------- | ---------------------------- |
| `get_notifications` | GET `/api/message/v1/notifications` | 获取系统通知                 |
| `walk_folder`       | (组合 browse_folder 递归)           | 递归遍历文件夹，收集所有文件 |

### 5. 枚举类型

| 枚举             | 类型  | 值                                                                      | 说明           |
| ---------------- | ----- | ----------------------------------------------------------------------- | -------------- |
| `SortField`      | `str` | `NAME`, `TIME`, `SIZE`                                                  | 排序字段       |
| `SortDirection`  | `str` | `ASC`, `DESC`                                                           | 排序方向       |
| `ObjectMode`     | `str` | `ALL`, `FILES`, `DIRS`                                                  | 浏览模式过滤   |
| `DocLibType`     | `str` | `USER`, `SHARED_USER`, `GROUP`                                          | 文档库类型     |
| `OnDup`          | `int` | `FORBID=0`, `RENAME=1`, `OVERWRITE=3`                                   | 文件名冲突策略 |
| `CsfLevel`       | `int` | `LOW=0`, `INTERNAL=5`, `CONFIDENTIAL=6`, `SECRET=7`, `TOP_SECRET=8`     | 安全定级       |
| `PermissionType` | `str` | `DISPLAY`, `PREVIEW`, `DOWNLOAD`, `CREATE`, `MODIFY`, `DELETE`, `CACHE` | 权限类型       |

### 6. 异常类型

| 异常类                 | 说明                                                     |
| ---------------------- | -------------------------------------------------------- |
| `AnyShareError`        | 所有异常的基类                                           |
| `AnyShareNetworkError` | 网络层错误（连接失败、超时）                             |
| `AnyShareAuthError`    | 认证/授权失败（401, 403）                                |
| `AnyShareAPIError`     | API 返回的错误（含 `code`, `cause`, `status_code` 字段） |
| `AnyShareInputError`   | 用户输入无效（如非法 GNS 路径）                          |

### 7. 路径解析

AnyShare 使用 `gns://` 格式的内部路径标识对象。格式为：

```
gns://{doc_lib_id}/{folder_id}/.../{file_or_folder_id}
```

库提供 `anyshare_unofficial.utils.gns` 模块中的辅助函数：
- `is_gns_path(path)` — 验证 GNS 路径
- `parse_gns_path(path)` — 拆分为段列表
- `build_gns_path(*segments)` — 从段构建
- `quote_gns_path(path)` — URL 编码

## 许可证 <sub>Licensing</sub>

本项目基于 **MIT 开源许可证**，详情参见 [LICENSE](LICENSE) 页面。
