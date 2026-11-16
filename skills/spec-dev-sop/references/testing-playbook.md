# 单测设计手册

阶段 5 使用。目标不是「有测试」，而是「测试能抓住真正会出的事」。

## 九类矩阵展开

### 1 正常路径

主流程返回值、状态码、落库结果各一个断言。**不要只断言 `200`**，要断言响应体里的关键字段和数据库里的实际值。

### 2 边界值

- 数字：0、负数、1、最大值、超过最大值、浮点精度（`0.1 + 0.2`）
- 字符串：空串、单空格、纯空白、超长（超过字段长度）、含 emoji、含中文、含 `%` `_`（LIKE 通配）
- 分页：第 1 页、最后一页、超出总页数、`page_size` 为 0 或负数、总数恰好等于 page_size
- 时间：跨天/跨月/跨年、时区切换、闰年 2 月 29 日、夏令时
- 集合：空列表、单元素、重复元素

### 3 空值与类型

`None` / `null`、缺字段、字段名写错、`"1"` 与 `1`、布尔与 0/1、数组传成对象。前端还要测接口返回 `null` 时模板是否崩。

### 4 异常路径

- 数据库不可用、超时、死锁
- 第三方接口超时、返回 500、返回非 JSON
- 文件不存在、权限不足
- 事务中途失败 → **断言已写入的部分被回滚**

### 5 权限（最容易漏，也最致命）

| 场景 | 期望 |
| --- | --- |
| 未带 token | 401 |
| token 过期/伪造 | 401 |
| 角色无权限 | 403 |
| **用户 A 访问用户 B 的资源** | 404 或 403（绝不许 200） |
| 普通用户调管理员接口 | 403 |
| 前端隐藏了按钮但直接调接口 | 后端仍要拦 |

IDOR 专项写法（DRF）：

```python
def test_查询他人订单返回404(self):
    other = Order.objects.create(user=self.other_user, ...)
    self.client.force_authenticate(self.user)
    resp = self.client.get(f"/api/orders/{other.id}/")
    self.assertEqual(resp.status_code, 404)
```

### 6 并发与幂等

- 同一请求重复提交两次 → 只产生一条记录（或用幂等键去重）
- 两个请求同时扣减库存 → 不出现负库存（用事务 + 行锁，测试里用 `transaction.atomic` 加并发线程或至少断言唯一约束）
- 唯一约束冲突 → 返回 409 而不是 500

### 7 安全

- **SQL 注入**：`' OR '1'='1`、`1; DROP TABLE`、unicode 变形；用 ORM 就不必逐条测，但原生 SQL 必须测
- **XSS**：`<script>alert(1)</script>`、`<img src=x onerror=alert(1)>`，断言输出被转义
- **路径穿越**：`../../etc/passwd`、`..%2f`、绝对路径
- **文件上传**：伪造扩展名（`a.php` 改名 `a.jpg`）、超大文件、zip 炸弹
- **敏感信息外泄**：断言响应体和日志里**不出现**密码哈希、token、完整手机号
- **越权**：见第 5 类

### 8 数据一致性

失败回滚、软删除后列表不可见但详情按策略返回、级联删除不产生孤儿、批量操作部分失败的处理。

### 9 兼容

老字段缺失能否正常解析、老版本请求是否仍被接受、新增必填字段有没有默认值、时间格式变更是否兼容。

## Django / DRF 写法要点

```python
from django.test import TestCase
from rest_framework.test import APIClient

class XxxTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(...)

    def test_xxx_正常返回(self):
        ...
```

- 用 `TestCase`（自带事务回滚），不要用 `TransactionTestCase` 除非测事务行为本身
- 时间冻结：`unittest.mock.patch("django.utils.timezone.now", return_value=...)`
- 外部 HTTP：`responses` 或 `unittest.mock.patch`，**只 mock 外部依赖**
- 断言查询次数：`with self.assertNumQueries(3):` —— 防 N+1
- 测配置读取不要真读 `.env`，用 `override_settings`

## Vue 3 写法要点

```js
import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'

it('提交中禁用按钮防止重复提交', async () => {
  const wrapper = mount(Login, { global: { plugins: [router, pinia] } })
  await wrapper.find('button').trigger('click')
  expect(wrapper.find('button').attributes('disabled')).toBeDefined()
})
```

- 只 mock 网络层（`vi.mock('@/api/xxx')`），不要 mock 被测组件自身逻辑
- 必须覆盖四态：加载中、成功、失败、空数据
- 断言用户可见的文字，而不是内部 `data` 变量
- 列表渲染断言 `length` 与首项内容，不要只断言存在

## 命名与结构

- 命名说清场景：`test_登录_密码错误返回401`、`it('分页_超出总页数返回空列表')`
- 一个测试一个断言意图；多个断言必须是同一意图的不同侧面
- 遵循 AAA：Arrange（准备）、Act（执行）、Assert（断言），中间不要夹逻辑
- 测试里不要有 `sleep`、不要依赖执行顺序、不要依赖真实网络和当前时间

## 覆盖率

- 新增/修改的核心逻辑行覆盖率 ≥ 80%，分支覆盖率尽量 ≥ 70%
- 覆盖率是下限不是目标：100% 覆盖率照样可以漏掉越权
- 覆盖率不达标要么补测试，要么在测试记录里写明原因
