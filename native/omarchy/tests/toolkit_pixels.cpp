// Owned public fixture: exercise original Hyprtoolkit rendering and native input.
#include <hyprtoolkit/core/Backend.hpp>
#include <hyprtoolkit/core/Timer.hpp>
#include <hyprtoolkit/element/Rectangle.hpp>
#include <hyprtoolkit/window/Window.hpp>
#include <cstdio>

using namespace Hyprtoolkit;
using namespace Hyprutils::Memory;

static CSharedPointer<IBackend> backend;
static CSharedPointer<CRectangleElement> top, bottom;
static unsigned ticks = 0;
static bool clicked = false;
static std::string typed;

static void tick() {
    backend->addTimer(std::chrono::milliseconds(60), [](auto, void*) {
        ++ticks;
        const bool ready = clicked && typed == "loopy" && ticks >= 24;
        top->rebuild()->color([ready] { return ready ? CHyprColor{1.F, 0.F, 0.F} : CHyprColor{0.F, 0.F, 1.F}; })->commence();
        bottom->rebuild()->color([ready] { return ready ? CHyprColor{0.F, 1.F, 0.F} : CHyprColor{0.F, 0.F, ticks % 2 ? 0.5F : 1.F}; })->commence();
        if (ready) {
            std::fprintf(stdout, "fixture-ready clicked=true typed=loopy ticks=%u\n", ticks);
            std::fflush(stdout);
        } else if (ticks < 120)
            tick();
    }, nullptr);
}

int main() {
    backend = IBackend::create();
    if (!backend)
        return 70;
    auto window = CWindowBuilder::begin()->type(HT_WINDOW_LAYER)->preferredSize({0, 0})
        ->appClass("loopy-owned-toolkit-pixels")->layer(2)->anchor(15)->exclusiveZone(-1)->kbInteractive(1)->commence();
    top = CRectangleBuilder::begin()->color([] { return CHyprColor{0.F, 0.F, 1.F}; })
        ->size({CDynamicSize::HT_SIZE_PERCENT, CDynamicSize::HT_SIZE_PERCENT, {1.F, 0.5F}})->commence();
    bottom = CRectangleBuilder::begin()->color([] { return CHyprColor{0.F, 0.F, 1.F}; })
        ->size({CDynamicSize::HT_SIZE_PERCENT, CDynamicSize::HT_SIZE_PERCENT, {1.F, 0.5F}})->commence();
    top->setPositionFlag(IElement::HT_POSITION_FLAG_TOP, true);
    bottom->setPositionFlag(IElement::HT_POSITION_FLAG_BOTTOM, true);
    for (const auto& rect : {top, bottom}) {
        rect->setPositionMode(IElement::HT_POSITION_ABSOLUTE);
        rect->animateColor(SNoAnimation{});
        rect->setReceivesMouse(true);
        rect->setMouseButton([](Input::eMouseButton button, bool down) {
            if (button == Input::MOUSE_BUTTON_LEFT && !down)
                clicked = true;
        });
        window->m_rootElement->addChild(rect);
    }
    window->m_events.keyboardKey.listenStatic([](Input::SKeyboardKeyEvent event) {
        if (event.down && event.utf8.size() == 1 && event.utf8[0] >= 'a' && event.utf8[0] <= 'z' && typed.size() < 16)
            typed += event.utf8;
    });
    window->open();
    tick();
    backend->enterLoop();
    return 0;
}
