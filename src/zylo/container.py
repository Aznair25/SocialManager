"""The composition root.

This is the one place that names concrete adapters. Everything else takes its
collaborators through its constructor, so swapping OpenAI for another provider,
or Playwright for another screenshotter, is an edit to this file alone.

Tests build a container with fakes passed in, which is why every adapter is an
optional constructor argument rather than something built unconditionally.
"""
from functools import cached_property

from .adapters.browser import PlaywrightPageFetcher, PlaywrightScreenshotEngine
from .adapters.extraction import WebPageSourceExtractor
from .adapters.openai_client import OpenAIChatClient
from .adapters.storage import FileSystemDeckRepository
from .config import Paths, Settings
from .domain.validation import DeckValidator
from .prompts.builder import PromptBuilder
from .prompts.frameworks import FrameworkCatalog
from .rendering.assets import FontResolver
from .rendering.contact_sheet import ContactSheetHtmlBuilder
from .rendering.slides import SlideHtmlBuilder
from .rendering.templates import TemplateRepository
from .rendering.theme import CssVariableBuilder, Theme
from .services.generation import DeckGenerationService
from .services.jobs import JobRunner, JobStore
from .services.pipeline import DeckPipeline
from .services.rendering import DeckRenderingService


class ApplicationContainer:
    """Lazily builds the object graph. Nothing is constructed until it is asked for,
    so a CLI `validate` run never touches Playwright or the OpenAI SDK."""

    def __init__(self, settings: Settings | None = None, *,
                 chat_client=None, screenshot_engine=None, page_fetcher=None,
                 source_extractor=None, repository=None):
        self.settings = settings or Settings.from_env()
        self._chat_client = chat_client
        self._screenshot_engine = screenshot_engine
        self._page_fetcher = page_fetcher
        self._source_extractor = source_extractor
        self._repository = repository

    @classmethod
    def default(cls) -> "ApplicationContainer":
        return cls(Settings.from_env())

    # -- configuration ------------------------------------------------------

    @property
    def paths(self) -> Paths:
        return self.settings.paths

    # -- domain -------------------------------------------------------------

    @cached_property
    def validator(self) -> DeckValidator:
        return DeckValidator.with_default_rules()

    @cached_property
    def frameworks(self) -> FrameworkCatalog:
        return FrameworkCatalog.default()

    @cached_property
    def prompts(self) -> PromptBuilder:
        return PromptBuilder(self.frameworks)

    # -- rendering ----------------------------------------------------------

    @cached_property
    def theme(self) -> Theme:
        return Theme.load(self.paths.tokens_file, self.paths.brand)

    @cached_property
    def templates(self) -> TemplateRepository:
        return TemplateRepository(self.paths.templates)

    @cached_property
    def fonts(self) -> FontResolver:
        return FontResolver(self.paths.fonts)

    @cached_property
    def slide_builder(self) -> SlideHtmlBuilder:
        return SlideHtmlBuilder(self.theme, self.templates, self.fonts,
                                CssVariableBuilder(self.theme))

    @cached_property
    def contact_sheet_builder(self) -> ContactSheetHtmlBuilder:
        return ContactSheetHtmlBuilder(self.theme, self.fonts)

    # -- adapters -----------------------------------------------------------

    @cached_property
    def repository(self) -> FileSystemDeckRepository:
        return self._repository or FileSystemDeckRepository(self.paths.decks)

    @cached_property
    def chat_client(self) -> OpenAIChatClient:
        return self._chat_client or OpenAIChatClient(self.settings.model)

    @cached_property
    def screenshot_engine(self) -> PlaywrightScreenshotEngine:
        return self._screenshot_engine or PlaywrightScreenshotEngine()

    @cached_property
    def page_fetcher(self) -> PlaywrightPageFetcher:
        return self._page_fetcher or PlaywrightPageFetcher()

    @cached_property
    def source_extractor(self) -> WebPageSourceExtractor:
        return self._source_extractor or WebPageSourceExtractor(self.page_fetcher)

    # -- services -----------------------------------------------------------

    @cached_property
    def generator(self) -> DeckGenerationService:
        return DeckGenerationService(chat=self.chat_client, validator=self.validator,
                                     prompts=self.prompts,
                                     max_attempts=self.settings.max_attempts)

    @cached_property
    def renderer(self) -> DeckRenderingService:
        return DeckRenderingService(engine=self.screenshot_engine, validator=self.validator,
                                    slides=self.slide_builder,
                                    contact_sheet=self.contact_sheet_builder,
                                    theme=self.theme, repository=self.repository,
                                    paths=self.paths)

    @cached_property
    def pipeline(self) -> DeckPipeline:
        return DeckPipeline(generator=self.generator, renderer=self.renderer,
                            validator=self.validator, repository=self.repository,
                            extractor=self.source_extractor, paths=self.paths)

    @cached_property
    def jobs(self) -> JobStore:
        return JobStore()

    @cached_property
    def job_runner(self) -> JobRunner:
        return JobRunner(self.jobs)
