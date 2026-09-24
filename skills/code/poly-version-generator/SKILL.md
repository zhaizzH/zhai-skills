---
name: poly-version-generator
description: "管理「同一目标、N 个对照版本」项目的目录存放规范。当一个目标要用多种风格独立实现并横向对比、需要在版本区里建立 v01~vNN 目录结构、或要审计已有版本的文件布局是否符合规范时使用。单一 profile poly-version：版本根只锁 src/，内部结构不限；入口名与必需产物清单可由区文档的配置行覆盖，故换语言或换实验不必改脚本。典型场景是课程实验的多版本对照（如《算法设计与分析》同一实验的五个写法），各份要能当各自独立的提交交出去。只管目录存放，不管代码怎么写。"
---

# 多版本对照项目的目录规范

## 这个技能解决什么

一个目标用 N 种风格各写一遍、横向对比，产物会散成一堆目录。这个技能只回答一个问题：

> **第 N 个版本的产物放在哪、叫什么名字？**

**不管代码怎么写。** 抽象方式、模块拆分、命名细节、依赖选择各版自定 —— 那正是风格差异的来源。
规范只保证一件事：**同一目标下各版整体结构相同**，`diff v01/src v02/src` 有锚点。

## 唯一真源

目录规范的真源是**一个文件**：

```
poly-version-generator/scripts/audit_layout.py
```

里面的 `POLY_VERSION` 这个 `Profile` 就是规范本身。本文件和各区
`项目总结.md` 的第一节都是它的派生 —— **不要手抄一份树到别处**。

配套参考（按需查阅，不必通读）：

| 文件 | 何时看 |
|---|---|
| [`references/rules.md`](references/rules.md) | 想知道某条硬性规则的完整清单与理由 |
| [`references/troubleshooting.md`](references/troubleshooting.md) | 审计报错时对照处理 |

## 两套 profile：`poly-version` / `source-snapshot`

版本区在区根文档里声明自己用哪套规矩（一行 `` - `profile` = `poly-version` ``），
审计器自己读。

| | `poly-version` | `source-snapshot` |
|---|---|---|
| 版本是什么 | 同一目标的若干独立实现，整体结构相同、内部细节各异 | 同一份代码的 N 个**冻结快照**，逐版独立演进 |
| 版本根锁什么 | 只有 `src/` | 只有 `src/` |
| `src/` 内部 | **不管** —— 几个子目录、几个源文件、怎么分包一律自定 | 同左 |
| 行数上限 | 无 | 无 |
| 交付源码用词检查 | 有（版本号/风格名/模式名/「契约」+ 文件头编译运行命令） | **无**（快照内容来自既有代码，不该按新写代码的用词规矩审） |
| 截图与提交包 | 由 `batch-screenshot-submit` 技能负责 | 同左 |

**两套 profile 的区别只在用词检查**：`source-snapshot` 的源文件是既有代码的
冻结副本，强加「源码里不许带版本号」之类的规矩会把快照改到与原件不符 ——
那正好毁掉快照的意义。

> 区文档没写 `profile` 行时按 `poly-version` 审，并在输出里提示补一行。
> `--profile <名>` 可显式指定。

## 配置行：换语言 / 换实验的入口

区文档里的 `` - `键` = `值` `` 行有三类，**形状即语义**：

| 形状 | 含义 | 例 |
|---|---|---|
| `` `profile` `` | 选哪套规矩 | `` - `profile` = `poly-version` `` |
| `` `<Xxx>` ``（带尖括号） | 占位符映射：把规范里的占位符指到本实验的实际名 | `` - `<Xxx>` = `SingletonDemo` `` |
| 其它标识符 | **配置覆盖**（下表，全部可选） | `` - `entry` = `<Xxx>Experiment.java` `` |

| 配置键 | 缺省 | 作用 |
|---|---|---|
| `entry` | 空（不锁具体入口名） | 入口文件模式，**换语言就改这里** |
| `required` | 见 profile（`src/`） | 版本根必需项，**写了就只查列出的这些**。清单写法见下 |
| `java_checks` | `on` | `on`/`off`：交付用词与「头部编译运行命令」检查 |

**不写任何配置行 = 用 profile 的缺省。**

清单键三种写法等价（反引号对内逗号分隔 / 每值一对反引号 / 分多行）。

```markdown
- `profile` = `poly-version`
- `<Xxx>` = `MergeSort`
- `entry` = `<Xxx>Experiment.java`
```

## 三种用法

### 1. 建新版本区

1. 在仓库里建版本区目录 `poly-<实验>/`（如 `poly-merge-sort/`）。
2. 建 `项目总结.md`，先写映射行与需要的配置行（见上一节）。
3. 生成规范节，替掉占位内容：

   ```bash
   A=poly-version-generator/scripts/audit_layout.py
   python $A <版本区> --emit-spec -o spec.md
   ```

   生成物自带首尾边界（首行 `<!-- 本节由 poly-version-generator/scripts/audit_layout.py --emit-spec 生成，勿手改 -->`、末行
   `<!-- 本节结束 -->`）。**只替换「一、目录与文件树」这一节**：首行标记到末行
   标记整段换掉，其余各节原样保留。
4. 写完 `项目总结.md` 的其余三节（见下）。

### 2. 只留一份文档：`项目总结.md`

**整个版本区只有这一份 md，版本目录里一份不留。** 四块内容与来源：

| 块 | 原属 | 记什么 |
|---|---|---|
| 一、目录与文件树 | `CONTRACT.md` 第一节 | `--emit-spec` 生成，勿手改 |
| 二、版本→风格映射 + 各版状态 | `PLAN.md` | 要做几版、各是什么、做到哪一步 |
| 三、各版实际产出与取舍 | 每版 `MANIFEST.md` | 这版实际有什么、为什么多/少一个文件、校验记录 |
| 四、横向结论 | `REPORT.md` | 比下来谁赢在哪儿 |

**少写文档 ≠ 少记信息。** 最容易丢的是**「这版为什么多/少一个文件」** ——
`diff` 只显示两版差在哪，不说明那是有意为之还是漏了；解释必须落在第三块里。

### 3. 检查代码（必须先过）

**编译不通过、同类名冲突、out 被兄弟版本污染时，写报告 / 打包 / 横向对比都是白做。**
所以顺序是：**先检查代码，全 PASS 之后再审计布局。**

```bash
C=poly-version-generator/scripts/check_code.py
python $C <版本区>
python $C <版本区> --only v03      # 只查一个
```

检查四类真实故障：重复类名（按「包 + 类名」判，不同包同名合法）、未解析的本树
`import`、整套编译（`javac $(find src -name '*.java')`，绝不只编入口）、
`out/` 是否被污染。编译输出固定到 `out/<版本名>/`，**每版一个独立目录**。

`--out-root <目录>` 换编译输出根（默认 `<版本区>/out`）；`--javac <路径>` 换编译器。
两个选项都是给调用方钩子：被 `batch-screenshot-submit` 调时，它会传**每区专属的
out 根**（避免各区版本名都是 `v01`…`v05` 而互相误判）和**已定好的 JDK**。
自带跑不用传这两项。

结果写进各版 `vNN/check_code.txt`（首行 `√`/`×`）。**布局审计（下一步）读它当门。**
退出码 0 = 全 PASS，1 = 有版本 FAIL。

### 4. 审计布局

每批版本做完后跑一遍：

```bash
A=poly-version-generator/scripts/audit_layout.py
python $A <版本区>
python $A <版本区> --only v03             # 只审一个
```
退出码 0 = 全 PASS，1 = 有版本 FAIL。输出是逐版本的 PASS/FAIL 表，
样例见 [`references/troubleshooting.md`](references/troubleshooting.md) 开头。

- **区根文档**单独一块：`CONTRACT.md`/`PLAN.md`/`REPORT.md` 只要还在就会被报 ——
  判据是**文件存在**，不是内容为空。
- 审计只查「放哪、叫什么」加交付用词，**不看功能实现**。

## 核心约束速查

完整的表与逐条理由见 [`references/rules.md`](references/rules.md)。最常撞上的几条：

- 区根只有一份 `项目总结.md`，版本目录里**不放任何 md**；
- 版本根只有 `src/`，其余顶层文件/目录一律 FAIL；
- 交付源码里不得出现版本号/风格名/模式名/「契约」，也不得在文件头抄编译运行命令
  （有机器检查，可用 `java_checks` = `off` 关闭）；
- 各版 `src/` 内部结构自定，但**整体结构要一致**，`diff` 才有锚点；
- 编译产物与临时文件一律忽略，**所以 `javac` 跑过之后再审计也能 PASS**；
- **一版 = 一个 out 目录 = 一个工作目录**，绝不共用 `out/`；整套编译，绝不只编入口；
- **代码检查（`check_code.py`）没全 PASS 不得进入下一步** —— `audit_layout.py` 读各版
  `check_code.txt` 当门，缺文件或首行不是 `√` 都 FAIL。

## 与实验报告技能的分工

本技能**只管道内**：版本区 `poly-<实验>/` 与其下的 `vNN/`。
仓库根那些顶层目录（如课程提交目录）归**报告类技能**管，本技能不碰。

## 与 `batch-screenshot-submit` 的分工

| 技能 | 管什么 |
|---|---|
| 本技能 | 版本区**放在哪、叫什么**（目录布局）；并提供 `check_code.py` 当前置检查 |
| `batch-screenshot-submit` | 让版本区**跑起来、截到图、打成可提交的包** |

两者可以对接：截图技能在编译前会先跑本技能的 `check_code.py`，
未全 PASS 就整体中止。**截图技能不改本技能管的任何源文件。**

## 自检

两个脚本各带一份不依赖真实版本区的判据自检：

```bash
python poly-version-generator/scripts/test_check_code.py
python poly-version-generator/scripts/test_audit_layout.py
```

改动 `check_code.py` / `audit_layout.py` 后跑一遍，都输出 `SELF-CHECK OK` 才算改对了。
`test_audit_layout.py` 盯的是一处真实踩过的假阳性：二进制资源（`src/img/*.jpg`）
被当源码做用词检查，字节凑出 `v30` 让整批版本误报。
