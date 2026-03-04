# 架构师代码审查 Prompt 更新总结

## 执行摘要

本次更新为架构师角色添加了**全面的代码审查能力**，覆盖代码规范（阿里 Java 开发手册）、安全性、性能、架构一致性四大维度，并**移除了强制 DDD 的要求**，使架构师能够进行更专业、更系统的代码评审。

**更新日期**: 2026-03-04  
**更新范围**: SKILL.md - 架构师 Prompt  
**主要改进**: 代码规范审查、安全审查、性能审查、架构一致性审查

---

## 一、核心更新内容

### 1.1 职责定义增强

**更新前**:
```
职责：设计系统性、前瞻性、可落地、可验证的架构
```

**更新后**:
```
职责：设计系统性、前瞻性、可落地、可验证的架构，确保代码质量、安全性和架构一致性
```

**新增触发关键词**:
- "代码评审"
- "代码规范"
- "安全检查"
- "性能优化"

**新增典型任务**:
- 关键代码的架构审查和代码评审
- 代码规范和安全检查

### 1.2 新增代码审查规则（第 6 节）

#### 6.1 代码规范审查（阿里 Java 开发手册标准）

**4 个审查维度**:

1. **命名规范** (6.1.1)
   - 类名：UpperCamelCase（DO/BO/DTO/VO 后缀）
   - 方法名：lowerCamelCase
   - 常量名：UPPER_CASE
   - 包名：小写
   - 类型参数：单个大写字母
   - 抽象类：Abstract/Base 开头
   - 异常类：Exception 结尾
   - 测试类：Test 结尾

2. **代码格式** (6.1.2)
   - 4 空格缩进（禁止 Tab）
   - 单行不超过 120 字符
   - 操作符前后空格
   - 大括号前后空格
   - 空行规范

3. **注释规范** (6.1.3)
   - 类、方法必须有 Javadoc
   - 参数、返回值必须说明
   - 复杂逻辑必须有行内注释
   - 禁止注释掉的代码
   - 禁止无意义注释

4. **OOP 规范** (6.1.4)
   - 访问权限控制
   - 禁止改变父类成员可见性
   - 覆写方法必须加@Override
   - final 只用于类、方法、常量

**示例对比**:
```java
// ✅ 正确
public class UserDO { }
public static final int MAX_COUNT = 100;

// ❌ 错误
public class userDO { }  // 类名小写
public static final int maxCount = 100;  // 常量小写
```

#### 6.2 安全性审查

**4 个审查维度**:

1. **SQL 注入防护** (6.2.1)
   - 禁止字符串拼接 SQL
   - 必须使用预编译语句
   - MyBatis 必须使用#{}而非${}
   - 动态 SQL 必须参数校验

2. **XSS 攻击防护** (6.2.2)
   - 用户输入必须 HTML 转义
   - 输出到页面必须转义
   - 使用安全的富文本库

3. **敏感信息保护** (6.2.3)
   - 密码加密存储（BCrypt/SCrypt）
   - 禁止日志打印敏感信息
   - 禁止硬编码密钥、密码
   - 敏感配置加密存储
   - 接口必须鉴权

4. **权限控制** (6.2.4)
   - 所有接口必须身份认证
   - 所有操作必须权限校验
   - 禁止越权访问
   - 水平越权检查
   - 垂直越权检查

**示例对比**:
```java
// ❌ 错误 - SQL 注入风险
String sql = "SELECT * FROM user WHERE id = " + userId;

// ✅ 正确 - 预编译
String sql = "SELECT * FROM user WHERE id = ?";
PreparedStatement ps = conn.prepareStatement(sql);
ps.setLong(1, userId);
```

#### 6.3 性能审查

**4 个审查维度**:

1. **数据库性能** (6.3.1)
   - SQL 必须有索引
   - 禁止 N+1 查询
   - 批量操作使用批量 API
   - 禁止 SELECT *
   - 大表分页优化

2. **缓存使用** (6.3.2)
   - 热点数据必须缓存
   - 缓存必须有过期时间
   - 缓存穿透防护
   - 缓存雪崩防护
   - 缓存击穿防护

3. **并发处理** (6.3.3)
   - 禁止使用过时并发 API
   - 线程池合理配置
   - 并发集合替代同步集合
   - 锁粒度尽可能小
   - 避免死锁

4. **资源管理** (6.3.4)
   - 流必须关闭（try-with-resources）
   - 数据库连接必须释放
   - HTTP 连接必须关闭
   - 文件操作必须关闭流

**示例对比**:
```java
// ❌ 错误 - N+1 查询
List<User> users = userMapper.findAll();
for (User user : users) {
    List<Order> orders = orderMapper.findByUserId(user.getId());
}

// ✅ 正确 - 关联查询
@Select("SELECT u.*, o.* FROM user u LEFT JOIN orders o ON u.id = o.user_id")
List<UserOrder> findAllWithOrders();
```

#### 6.4 架构一致性审查

**4 个审查维度**:

1. **分层架构** (6.4.1)
   - Controller 层：只处理 HTTP 协议
   - Service 层：业务逻辑
   - Repository/DAO 层：数据访问
   - 禁止跨层调用
   - 禁止循环依赖

2. **依赖倒置** (6.4.2)
   - 模块间依赖抽象接口
   - 禁止依赖具体实现
   - 面向接口编程

3. **单一职责** (6.4.3)
   - 一个类只有一个引起变化的原因
   - 方法职责单一
   - 类的大小合理（<500 行）
   - 方法的大小合理（<50 行）

4. **接口设计** (6.4.4)
   - 接口定义清晰、职责单一
   - 接口参数不超过 5 个
   - 接口返回值明确
   - 异常定义清晰
   - 接口版本管理

**示例对比**:
```
✅ 正确的分层:
Controller → Service → Repository

❌ 错误的调用:
Controller → Repository (跨层)
Repository → Service (反向依赖)
```

### 1.3 审查流程规范（6.5 节）

**三步审查流程**:

1. **自动检查**（使用工具）
   - 编译检查：`mvn clean compile`
   - 代码规范：`mvn checkstyle:check`
   - 静态分析：`mvn spotbugs:check`
   - 单元测试：`mvn test`

2. **人工审查**（架构师执行）
   - 代码规范审查（6.1）
   - 安全性审查（6.2）
   - 性能审查（6.3）
   - 架构一致性审查（6.4）

3. **审查输出**
   - 审查报告（问题清单）
   - 严重程度分级（Critical/Major/Minor）
   - 修复建议
   - 修复期限

**问题分级标准**:

| 级别 | 问题类型 | 处理要求 |
|-----|---------|---------|
| **Critical** | 安全漏洞、严重性能问题、架构违规 | 立即修复，禁止上线 |
| **Major** | 代码规范违反、潜在性能问题、缺少错误处理 | 本周内修复 |
| **Minor** | 注释不完整、代码可读性问题 | 下次迭代修复 |

### 1.4 审查报告模板（6.6 节）

**完整模板结构**:
```markdown
# 代码审查报告

## 基本信息
- 项目名称
- 审查日期
- 审查人
- 审查范围

## 审查结果汇总
- 总问题数
  - Critical: [数量]
  - Major: [数量]
  - Minor: [数量]

## 问题清单
### Critical 问题
#### 问题 1: [问题名称]
- 位置
- 描述
- 代码示例
- 建议
- 修复期限

### Major 问题
...

### Minor 问题
...

## 审查结论
- [ ] 通过，可以上线
- [ ] 有条件通过（Major 问题修复后上线）
- [ ] 不通过（Critical 问题修复后重新审查）

## 签字确认
- 审查人签字
- 开发负责人签字
```

---

## 二、移除内容

### 2.1 移除强制 DDD 要求

**更新前**（综合分析报吿.md 中的建议）:
```markdown
### 5. 任务管理与自动继续规则
【复杂任务必须使用】
...
（注：原文档中包含强制 DDD 相关内容）
```

**更新后**:
- 移除了强制 DDD 的要求
- 架构师可以根据项目实际情况选择合适的架构模式
- 不再强制要求使用领域驱动设计

**原因**:
- DDD 不是唯一正确的架构模式
- 不同项目适合不同的架构方法
- 应该根据实际情况灵活选择

---

## 三、使用示例

### 示例 1: 代码规范审查

**用户请求**:
```
审查这段代码的规范性：
public class userservice{
    public static final int maxcount=100;
    public void doprocess(){
        //TODO
    }
}
```

**架构师审查**:
```
📋 代码规范审查报告

发现以下问题：

❌ Major 问题:
1. 类名违反命名规范
   - 位置：userservice
   - 问题：类名应该使用 UpperCamelCase
   - 建议：改为 UserService

2. 常量名违反命名规范
   - 位置：maxcount
   - 问题：常量名应该使用 UPPER_CASE
   - 建议：改为 MAX_COUNT

3. 方法名违反命名规范
   - 位置：doprocess
   - 问题：方法名应该使用 lowerCamelCase
   - 建议：改为 doProcess

4. 缺少 Javadoc 注释
   - 位置：类和方法
   - 问题：缺少 Javadoc 注释
   - 建议：添加完整的 Javadoc

审查结论：有条件通过（修复 Major 问题后上线）
```

### 示例 2: 安全性审查

**用户请求**:
```
审查这段代码的安全性：
public User login(String username, String password) {
    String sql = "SELECT * FROM user WHERE username='" + username + 
                 "' AND password='" + password + "'";
    return jdbcTemplate.queryForObject(sql, User.class);
}
```

**架构师审查**:
```
🚨 安全性审查报告

发现 Critical 问题：

❌ Critical: SQL 注入风险
- 位置：login 方法
- 问题：使用字符串拼接 SQL，存在 SQL 注入风险
- 风险等级：Critical
- 影响：攻击者可以绕过认证或获取敏感数据

建议修复：
```java
public User login(String username, String password) {
    String sql = "SELECT * FROM user WHERE username=? AND password=?";
    return jdbcTemplate.queryForObject(sql, User.class, username, password);
}
```

审查结论：不通过（Critical 问题必须立即修复）
```

### 示例 3: 性能审查

**用户请求**:
```
审查这段代码的性能：
List<Order> getAllOrdersWithUsers() {
    List<Order> orders = orderMapper.findAll();
    for (Order order : orders) {
        User user = userMapper.findById(order.getUserId());
        order.setUser(user);
    }
    return orders;
}
```

**架构师审查**:
```
⚡ 性能审查报告

发现 Major 问题：

❌ Major: N+1 查询问题
- 位置：getAllOrdersWithUsers 方法
- 问题：循环查询数据库，导致 N+1 次查询
- 影响：如果有 1000 个订单，将执行 1001 次 SQL 查询
- 性能影响：严重

建议修复：
```java
@Select("SELECT o.*, u.* FROM orders o " +
        "LEFT JOIN user u ON o.user_id = u.id")
List<OrderWithUser> findAllWithUsers();
```

审查结论：有条件通过（修复 Major 问题后上线）
```

### 示例 4: 架构一致性审查

**用户请求**:
```
审查这段代码的架构一致性：
@RestController
public class OrderController {
    @Autowired
    private OrderMapper orderMapper;
    
    @GetMapping("/orders/{id}")
    public Order getOrder(@PathVariable Long id) {
        return orderMapper.findById(id);
    }
}
```

**架构师审查**:
```
🏛️ 架构一致性审查报告

发现 Major 问题：

❌ Major: 跨层调用
- 位置：OrderController
- 问题：Controller 直接调用 DAO（OrderMapper），违反了分层架构
- 影响：业务逻辑泄露到控制层，不利于维护和测试

正确架构：
Controller → Service → Repository

建议修复：
```java
@RestController
public class OrderController {
    @Autowired
    private OrderService orderService;  // 依赖 Service 层
    
    @GetMapping("/orders/{id}")
    public Order getOrder(@PathVariable Long id) {
        return orderService.getOrderById(id);
    }
}

@Service
public class OrderService {
    @Autowired
    private OrderMapper orderMapper;
    
    public Order getOrderById(Long id) {
        return orderMapper.findById(id);
    }
}
```

审查结论：有条件通过（修复 Major 问题后上线）
```

---

## 四、工具集成建议

### 4.1 自动检查工具

**Maven 插件配置**:

```xml
<plugins>
    <!-- Checkstyle - 代码规范检查 -->
    <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-checkstyle-plugin</artifactId>
        <version>3.3.0</version>
        <configuration>
            <configLocation>checkstyle.xml</configLocation>
        </configuration>
    </plugin>
    
    <!-- SpotBugs - 静态分析 -->
    <plugin>
        <groupId>com.github.spotbugs</groupId>
        <artifactId>spotbugs-maven-plugin</artifactId>
        <version>4.7.3.5</version>
    </plugin>
    
    <!-- PMD - 代码质量检查 -->
    <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-pmd-plugin</artifactId>
        <version>3.21.0</version>
    </plugin>
</plugins>
```

### 4.2 Checkstyle 配置示例

```xml
<?xml version="1.0"?>
<!DOCTYPE module PUBLIC
    "-//Checkstyle//DTD Checkstyle Configuration 1.3//EN"
    "https://checkstyle.org/dtds/configuration_1_3.dtd">

<module name="Checker">
    <property name="charset" value="UTF-8"/>
    <property name="severity" value="warning"/>
    
    <module name="TreeWalker">
        <!-- 命名规范 -->
        <module name="TypeName"/>
        <module name="MethodName"/>
        <module name="ParameterName"/>
        <module name="ConstantName"/>
        
        <!-- 代码格式 -->
        <module name="LineLength">
            <property name="max" value="120"/>
        </module>
        
        <!-- 注释规范 -->
        <module name="JavadocMethod"/>
        <module name="JavadocType"/>
        
        <!-- OOP 规范 -->
        <module name="ModifierOrder"/>
        <module name="RedundantModifier"/>
    </module>
</module>
```

---

## 五、效果对比

### 5.1 审查能力对比

| 维度 | 更新前 | 更新后 |
|-----|-------|-------|
| **代码规范** | 无明确标准 | 阿里 Java 规范（4 维度） |
| **安全性** | 简单检查 | 全面审查（4 维度） |
| **性能** | 经验判断 | 系统化审查（4 维度） |
| **架构一致性** | 定性分析 | 结构化审查（4 维度） |
| **审查流程** | 随意 | 标准化三步流程 |
| **问题分级** | 无 | Critical/Major/Minor |
| **审查报告** | 口头 | 标准化模板 |

### 5.2 审查质量提升

**更新前**:
```
架构师："代码看起来不错，有一些小问题需要修复。"
开发者："什么问题？"
架构师："嗯...命名不太规范，还有一些性能问题。"
开发者："具体是哪些？"
架构师："我记不清了，你再去检查检查吧。"
```

**更新后**:
```
架构师："代码审查完成，发现 5 个问题。"

📋 审查报告:
- Critical: 1 个（SQL 注入风险）
- Major: 3 个（N+1 查询、跨层调用、缺少索引）
- Minor: 1 个（缺少 Javadoc）

请优先修复 Critical 问题，本周内修复 Major 问题。
```

---

## 六、最佳实践

### 6.1 审查时机

**必须审查的场景**:
- ✅ 核心业务代码
- ✅ 涉及资金安全的代码
- ✅ 涉及用户隐私的代码
- ✅ 性能敏感代码
- ✅ 公共库和框架代码
- ✅ 跨团队接口代码

**可以简化审查的场景**:
- ⚪ 简单的 CRUD 代码
- ⚪ 测试代码
- ⚪ 文档代码
- ⚪ 配置代码

### 6.2 审查频率

**推荐频率**:
- 核心代码：每次提交前审查
- 重要功能：每个 Sprint 审查
- 一般代码：每月抽查

### 6.3 审查文化

**建设性反馈**:
```
❌ 错误："这代码写得太差了"
✅ 正确："建议优化这段代码的性能，使用缓存可以减少数据库查询"

❌ 错误："你怎么又写了 SQL 注入？"
✅ 正确："这里存在 SQL 注入风险，建议使用预编译语句"

❌ 错误："重新写吧，问题太多了"
✅ 正确："发现了 3 个 Major 问题，修复后我可以帮你再审一次"
```

---

## 七、总结

### 7.1 核心成果

本次更新为架构师角色添加了以下核心能力：

1. **代码规范审查** ✅
   - 命名规范（阿里 Java 规范）
   - 代码格式
   - 注释规范
   - OOP 规范

2. **安全性审查** ✅
   - SQL 注入防护
   - XSS 攻击防护
   - 敏感信息保护
   - 权限控制

3. **性能审查** ✅
   - 数据库性能
   - 缓存使用
   - 并发处理
   - 资源管理

4. **架构一致性审查** ✅
   - 分层架构
   - 依赖倒置
   - 单一职责
   - 接口设计

5. **审查流程规范** ✅
   - 三步审查流程
   - 问题分级标准
   - 审查报告模板

### 7.2 移除内容

- ✅ 移除了强制 DDD 的要求
- ✅ 架构师可以灵活选择架构模式

### 7.3 使用建议

1. **根据项目规模选择审查粒度**
   - 大型项目：全面审查
   - 中型项目：重点审查（安全 + 性能）
   - 小型项目：简化审查（安全）

2. **结合自动化工具**
   - 使用 Checkstyle 自动检查代码规范
   - 使用 SpotBugs 自动检查潜在问题
   - 使用 SonarQube 进行持续质量监控

3. **建立审查文化**
   - 对事不对人
   - 建设性反馈
   - 持续改进

---

**文档版本**: v1.0  
**更新日期**: 2026-03-04  
**维护者**: Trae Multi-Agent Team  
**审核状态**: ✅ 已完成
