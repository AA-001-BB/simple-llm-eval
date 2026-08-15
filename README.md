# Simple LLM Evaluation

[![version](https://img.shields.io/github/v/release/cyberark/simple-llm-eval)](https://pypi.org/project/simpleval/)
![Build Status](https://github.com/cyberark/simple-llm-eval/actions/workflows/ci.yml/badge.svg)
![Code Coverage](https://raw.githubusercontent.com/cyberark/simple-llm-eval/refs/heads/badges/ci/badges/coverage-updated.svg)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/simpleval)
[![license](https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square)](https://raw.githubusercontent.com/cyberark/simple-llm-eval/refs/heads/main/LICENSE)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/cyberark/simple-llm-eval/badge)](https://scorecard.dev/viewer/?uri=github.com/cyberark/simple-llm-eval)

![Simpleval Banner](https://raw.githubusercontent.com/cyberark/simple-llm-eval/main/docs/media/simpleval-banner.jpeg)

Welcome to the simple LLM evaluation framework—**simpleval**, for short.

**simpleval** is a Python package designed to make evaluating Large Language Models (LLMs) easier, using the "LLM as a Judge" technique.

It supports a [variety of LLM providers](https://cyberark.github.io/simple-llm-eval/latest/getting-started/judge-authentication/), including OpenAI, Google (Gemini API, Vertex), AWS Bedrock, Anthropic, Azure, and more (via LiteLLM).

**simpleval** also includes several reports to help you analyze, compare, and summarize your evaluation results. See the [available reports](https://cyberark.github.io/simple-llm-eval/latest/getting-started/reporting/) for more details.

## 中文离线产品评测示例

查看[中文 AI 产品评测离线示例](docs/getting-started/product-eval-zh.md)，可使用本地手工 JSONL 夹具运行并比较结构化输出，全程不调用模型 API。这是基于 `cyberark/simple-llm-eval`（上游提交 `09c9fdad5f03014a6c3c1237ddd95eb0081934b5`）的衍生扩展，采用 Apache-2.0；`LICENSE` 和 `NOTICES` 保持不变。

> **指标边界：** 示例输出是手工编写的离线夹具。报告中的 `mean_score`、`improved` 和 `regressed` 只用于验证评测器与回归比较逻辑，不代表真实模型准确率、线上质量、用户结果或业务提升。

## Getting Started

See the [📚 Quickstart Guide 📚](https://cyberark.github.io/simple-llm-eval/latest/getting-started/quickstart/)

## Documentation

See [📚 Project Documentation 📚](https://cyberark.github.io/simple-llm-eval/)

## Contributing

We appreciate your help in making this project better! ✨

If you would like to contribute to this project, please follow the guidelines outlined in the [CONTRIBUTING.md](https://github.com/cyberark/simple-llm-eval/blob/main/CONTRIBUTING.md) file.

## License

simpleval is released under the [Apache License](https://www.apache.org/licenses/LICENSE-2.0). See the [LICENSE](https://github.com/cyberark/simple-llm-eval/blob/main/LICENSE) file for more details.

## Contact

If you have any questions or suggestions, feel free to join our [GitHub discussions forum](https://github.com/cyberark/simple-llm-eval/discussions) 💬

If you want to report a bug or request a feature, please open an issue in the [GitHub issues tracker](https://github.com/cyberark/simple-llm-eval/issues) 🐛

<br>
