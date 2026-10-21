//! Owned CPU fixture: real parent protocol, fixed geometry and actual display control.
use loopy_wayland::{display_target::DisplayTarget, pixels::Layout, scene::Layer, server::{Host, Target}};
use std::{io::{self, BufRead, Write}, path::Path, sync::mpsc, thread, time::{Duration, Instant}};

struct FixedTarget;
impl Target for FixedTarget {
    fn dimensions(&self) -> (i32, i32) { (640, 360) }
    fn render(&mut self, _: &Layout, _: &[u8]) -> io::Result<()> { Ok(()) }
    // No visual acceptance is claimed. Parent still receives real committed SHM snapshots.
    fn render_scene(&mut self, _: i32, _: i32, _: &[Layer]) -> io::Result<()> { Ok(()) }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().collect();
    if args.len() != 3 { return Err("usage: refresh_parent PRIVATE_SOCKET SECONDS".into()); }
    let seconds: u64 = args[2].parse()?;
    if !(1..=60).contains(&seconds) { return Err("duration must be 1..60 seconds".into()); }
    let (target, control) = DisplayTarget::attached(Box::new(FixedTarget))?;
    let token = control.token();
    if !control.refresh_rate(token, 120000) { return Err("initial refresh rejected".into()); }
    let mut host = Host::new(Path::new(&args[1]), Box::new(target))?;
    let start = Instant::now();
    println!("ready size=640x360 refresh_millihz=120000");
    io::stdout().flush()?;
    let (send, receive) = mpsc::sync_channel::<String>(16);
    thread::spawn(move || {
        for line in io::stdin().lock().lines().map_while(Result::ok) {
            if line.len() <= 32 && send.send(line).is_err() { break; }
        }
    });
    let deadline = start + Duration::from_secs(seconds);
    let mut quit = false;
    while !quit && Instant::now() < deadline {
        while let Ok(command) = receive.try_recv() {
            if command == "quit" { quit = true; }
            else if let Some(value) = command.strip_prefix("refresh:") {
                let rate: u32 = value.parse()?;
                println!("refresh millihz={rate} accepted={} frames={} millis={}",
                    control.refresh_rate(token, rate), host.frames(), start.elapsed().as_millis());
            } else if let Some(sequence) = command.strip_prefix("sample:") {
                let sequence: u32 = sequence.parse()?;
                println!("sample sequence={sequence} frames={} millis={}", host.frames(), start.elapsed().as_millis());
            }
            io::stdout().flush()?;
        }
        host.tick()?;
        thread::sleep(Duration::from_micros(500));
    }
    println!("finished frames={} client_error={:?}", host.frames(), host.client_error());
    Ok(())
}
