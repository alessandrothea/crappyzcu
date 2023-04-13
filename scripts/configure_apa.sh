
det=3
crate=3

for slot in $(seq 1 5); do
    for link in 0 1; do
        wib=${crate}0${slot}
        hermesbutler.py np04-wib-$wib enable -l ${link} --dis
    done
done

for slot in 1 2 3 4 5; do
    for link in 0 1; do
        wib=${crate}0${slot}
        hermesbutler.py np04-wib-${wib} enable -l $link --dis 
        hermesbutler.py np04-wib-${wib} udp-config -l $link np04-wib-${wib}-d${link} np02-srv-001-100G
        hermesbutler.py np04-wib-${wib} mux-config -l $link ${det} ${crate} $slot
        #hermesbutler.py np04-wib-${wib} fakesrc-config -l $link -n 4
        hermesbutler.py np04-wib-${wib} enable -l $link --en
        hermesbutler.py np04-wib-${wib} stats -l $link
    done
done