# Live2D 模型目录

把 Cubism 3/4 模型放在这里即可，客户端启动时会自动加载找到的第一个 `.model3.json`：

```
assets/models/
└─ hiyori/
   ├─ Hiyori.model3.json
   ├─ Hiyori.moc3
   ├─ Hiyori.2048/
   │  └─ texture_00.png
   └─ ...
```

约定：

- 模型文件、贴图、动作、表情按导出时的相对路径原样放进来；
- 目录名随意，客户端会递归查找 `*.model3.json`；
- 想指定某个模型时，设置环境变量 `MYDIGITALMAID_MODEL` 指向 `.model3.json` 的路径。

仓库里的 Hiyori 是 Live2D 官方 CubismWebSamples 示例模型，仅用于本地开发调试。
正式发布前请替换为你拥有授权的模型，并遵守 Live2D Cubism 的许可条款。
